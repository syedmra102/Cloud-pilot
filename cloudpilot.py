import os
import sys
import json
import time
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress
from dotenv import load_dotenv

load_dotenv()

console = Console()




def log_action(action_type, resource_id, details=""):
    """Logs actions to a local file for audit trail"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action_type,
        "resource_id": resource_id,
        "details": details
    }
    
    log_file = "cloudpilot.log"
    
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # If logging fails, don't crash the program
        pass
    
    # Also print to console
    print(f"[LOG] {action_type}: {resource_id} | {details}")


def confirm_action(message):
    """Asks user to confirm before destructive actions"""
    response = input(f"\n  {message} (yes/no): ").strip().lower()
    return response in ("yes", "y")


def get_session(region=None):
    try:
        region = region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        session = boto3.Session(region_name=region)
        session.client('sts').get_caller_identity()
        return session
    except NoCredentialsError:
        console.print("AWS credentials not found!", style="bold red")
        console.print("Run: aws configure")
        sys.exit(1)
    except ClientError as e:
        console.print(f"AWS Error: {e}", style="bold red")
        sys.exit(1)


def get_ec2_resource(region=None):
    session = get_session(region)
    return session.resource('ec2')


def get_ec2_client(region=None):
    session = get_session(region)
    return session.client('ec2')


def get_s3_resource():
    session = get_session()
    return session.resource('s3')


def get_s3_client():
    session = get_session()
    return session.client('s3')


def get_iam_client():
    session = get_session()
    return session.client('iam')


def get_iam_resource():
    session = get_session()
    return session.resource('iam')


def get_instance_name(instance):
    if instance.tags:
        for tag in instance.tags:
            if tag['Key'] == 'Name':
                return tag['Value']
    return "No Name"


def get_state_emoji(state):
    states = {
        'running': '🟢',
        'stopped': '🔴',
        'pending': '🟡',
        'stopping': '🟡',
        'shutting-down': '🟡',
        'terminated': '⚫'
    }
    return states.get(state, '⚪')


def get_hourly_cost(instance_type):
    costs = {
        't2.micro': 0.0116,
        't2.small': 0.023,
        't2.medium': 0.0464,
        't2.large': 0.0928,
        't3.micro': 0.0104,
        't3.small': 0.0208,
        't3.medium': 0.0416,
        't3.large': 0.0832,
    }
    return costs.get(instance_type, 0.05)


def get_monthly_cost(instance_type):
    return get_hourly_cost(instance_type) * 24 * 30





class EC2Manager:
    def __init__(self, region=None):
        self.region = region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.ec2_resource = get_ec2_resource(self.region)
        self.ec2_client = get_ec2_client(self.region)

    def get_latest_ami(self):
        try:
            response = self.ec2_client.describe_images(
                Owners=['amazon'],
                Filters=[
                    {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                    {'Name': 'state', 'Values': ['available']}
                ]
            )
            images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
            if images:
                return images[0]['ImageId']
            return 'ami-0c55b159cbfafe1f0'
        except Exception:
            return 'ami-0c55b159cbfafe1f0'

    def launch(self, name, instance_type='t3.micro', ami=None):
        console.print(f"\nLaunching EC2 instance '{name}'...\n", style="cyan")

        try:
            if not ami:
                ami = self.get_latest_ami()

            instances = self.ec2_resource.create_instances(
                ImageId=ami,
                InstanceType=instance_type,
                MaxCount=1,
                MinCount=1,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': name},
                            {'Key': 'ManagedBy', 'Value': 'CloudPilot'},
                            {'Key': 'LaunchedAt', 'Value': datetime.now().isoformat()}
                        ]
                    }
                ]
            )

            instance = instances[0]
            console.print("Waiting for instance to start...", style="yellow")
            instance.wait_until_running()
            instance.reload()

            hourly = get_hourly_cost(instance_type)
            monthly = get_monthly_cost(instance_type)

            console.print(Panel.fit(
                f"[bold green]Instance Launched Successfully![/bold green]\n\n"
                f"  Instance ID:  [cyan]{instance.id}[/cyan]\n"
                f"  Name:         [green]{name}[/green]\n"
                f"  Type:         [white]{instance_type}[/white]\n"
                f"  Public IP:    [yellow]{instance.public_ip_address or 'Assigning...'}[/yellow]\n"
                f"  Private IP:   [white]{instance.private_ip_address}[/white]\n"
                f"  Region:       [white]{self.region}[/white]\n"
                f"  Cost:         [red]${hourly:.4f}/hr (${monthly:.2f}/month)[/red]",
                title="CloudPilot - New Instance",
                border_style="green"
            ))

            log_action("LAUNCH", instance.id, f"{name} | {instance_type}")
            return instance

        except ClientError as e:
            console.print(f"Failed to launch: {e}", style="bold red")
            return None

    def list_instances(self, state_filter='all'):
        console.print(f"\nEC2 Instances ({self.region})\n", style="bold")

        instances = list(self.ec2_resource.instances.all())

        if not instances:
            console.print("  No instances found.", style="yellow")
            return []

        table = Table(
            title=f"EC2 Instances - {self.region}",
            show_header=True,
            header_style="bold cyan",
            border_style="blue"
        )
        table.add_column("State", width=8, justify="center")
        table.add_column("Instance ID", style="cyan", width=22)
        table.add_column("Name", style="green", width=18)
        table.add_column("Type", width=12)
        table.add_column("Public IP", width=16)
        table.add_column("Private IP", width=16)
        table.add_column("Cost/Month", style="red", width=12)

        running_count = 0
        stopped_count = 0
        total_monthly_cost = 0

        for instance in instances:
            state = instance.state['Name']

            if state_filter != 'all' and state != state_filter:
                continue

            if state == 'running':
                running_count += 1
            elif state == 'stopped':
                stopped_count += 1

            monthly = 0
            if state == 'running':
                monthly = get_monthly_cost(instance.instance_type)
                total_monthly_cost += monthly

            name = get_instance_name(instance)
            emoji = get_state_emoji(state)

            table.add_row(
                f"{emoji}",
                instance.id,
                name,
                instance.instance_type,
                instance.public_ip_address or "—",
                instance.private_ip_address or "—",
                f"${monthly:.2f}" if monthly > 0 else "—"
            )

        console.print(table)
        console.print(
            f"\n  Total: [green]{running_count} running[/green] | "
            f"[red]{stopped_count} stopped[/red] | "
            f"Est. cost: [red]${total_monthly_cost:.2f}/month[/red]\n"
        )

        return instances

    def find_instance(self, identifier):
        if identifier.startswith('i-'):
            try:
                instance = self.ec2_resource.Instance(identifier)
                instance.load()
                return instance
            except ClientError:
                console.print(f"Instance '{identifier}' not found", style="bold red")
                return None

        instances = self.ec2_resource.instances.filter(
            Filters=[
                {'Name': 'tag:Name', 'Values': [identifier]},
                {'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending']}
            ]
        )

        instance_list = list(instances)

        if not instance_list:
            console.print(f"No instance found with name '{identifier}'", style="bold red")
            return None

        if len(instance_list) > 1:
            console.print(f"Multiple instances found with name '{identifier}':", style="yellow")
            for inst in instance_list:
                console.print(f"  {inst.id} - {inst.state['Name']}")
            console.print("Please use instance ID instead.")
            return None

        return instance_list[0]

    def stop_instance(self, identifier):
        instance = self.find_instance(identifier)
        if not instance:
            return False

        name = get_instance_name(instance)

        if instance.state['Name'] != 'running':
            console.print(f"Instance '{name}' is already {instance.state['Name']}", style="yellow")
            return False

        if not confirm_action(f"Stop instance '{name}' ({instance.id})?"):
            console.print("Cancelled.", style="yellow")
            return False

        try:
            instance.stop()
            console.print(f"\nStopping '{name}' ({instance.id})...", style="yellow")
            instance.wait_until_stopped()

            hourly = get_hourly_cost(instance.instance_type)
            console.print(f"Instance stopped! You save ${hourly:.4f}/hour", style="green")

            log_action("STOP", instance.id, name)
            return True

        except ClientError as e:
            console.print(f"Failed to stop: {e}", style="bold red")
            return False

    def start_instance(self, identifier):
        instance = self.find_instance(identifier)
        if not instance:
            return False

        name = get_instance_name(instance)

        if instance.state['Name'] != 'stopped':
            console.print(f"Instance '{name}' is {instance.state['Name']}, cannot start", style="yellow")
            return False

        try:
            instance.start()
            console.print(f"\nStarting '{name}' ({instance.id})...", style="yellow")
            instance.wait_until_running()
            instance.reload()

            console.print(f"Instance started! IP: [cyan]{instance.public_ip_address}[/cyan]", style="green")

            log_action("START", instance.id, name)
            return True

        except ClientError as e:
            console.print(f"Failed to start: {e}", style="bold red")
            return False

    def terminate_instance(self, identifier):
        instance = self.find_instance(identifier)
        if not instance:
            return False

        name = get_instance_name(instance)

        if not confirm_action(f"PERMANENTLY TERMINATE '{name}' ({instance.id})? This CANNOT be undone!"):
            console.print("Cancelled.", style="yellow")
            return False

        try:
            instance.terminate()
            console.print(f"\nTerminating '{name}' ({instance.id})...", style="red")
            instance.wait_until_terminated()
            console.print("Instance terminated.", style="green")

            log_action("TERMINATE", instance.id, name)
            return True

        except ClientError as e:
            console.print(f"Failed to terminate: {e}", style="bold red")
            return False

    def terminate_all(self):
        instances = [i for i in self.ec2_resource.instances.all()
                     if i.state['Name'] not in ['terminated', 'shutting-down']]

        if not instances:
            console.print("No active instances to terminate.", style="yellow")
            return

        console.print(f"\nFound {len(instances)} active instances:\n", style="bold red")
        for inst in instances:
            console.print(f"  {get_instance_name(inst)} ({inst.id}) - {inst.state['Name']}")

        if not confirm_action(f"TERMINATE ALL {len(instances)} instances? This is IRREVERSIBLE!"):
            console.print("Cancelled.", style="yellow")
            return

        for inst in instances:
            name = get_instance_name(inst)
            try:
                inst.terminate()
                console.print(f"  Terminated: {name} ({inst.id})", style="red")
                log_action("TERMINATE", inst.id, name)
            except ClientError as e:
                console.print(f"  Failed: {name} - {e}", style="red")

        console.print("\nAll instances terminated. Monthly cost: $0.00", style="green")

    def instance_status(self, identifier):
        instance = self.find_instance(identifier)
        if not instance:
            return

        name = get_instance_name(instance)
        state = instance.state['Name']
        emoji = get_state_emoji(state)
        hourly = get_hourly_cost(instance.instance_type)
        monthly = get_monthly_cost(instance.instance_type)

        uptime = "—"
        if instance.launch_time and state == 'running':
            now = datetime.now(instance.launch_time.tzinfo)
            diff = now - instance.launch_time
            hours = int(diff.total_seconds() // 3600)
            minutes = int((diff.total_seconds() % 3600) // 60)
            uptime = f"{hours}h {minutes}m"

        sg_list = []
        if instance.security_groups:
            for sg in instance.security_groups:
                sg_list.append(f"{sg['GroupName']} ({sg['GroupId']})")

        console.print(Panel.fit(
            f"[bold]Instance Details[/bold]\n\n"
            f"  ID:           [cyan]{instance.id}[/cyan]\n"
            f"  Name:         [green]{name}[/green]\n"
            f"  {emoji} State:   [white]{state}[/white]\n"
            f"  Type:         [white]{instance.instance_type}[/white]\n"
            f"  Public IP:    [yellow]{instance.public_ip_address or 'None'}[/yellow]\n"
            f"  Private IP:   [white]{instance.private_ip_address or 'None'}[/white]\n"
            f"  Region:       [white]{self.region}[/white]\n"
            f"  Uptime:       [white]{uptime}[/white]\n"
            f"  Cost:         [red]${hourly:.4f}/hr (${monthly:.2f}/mo)[/red]\n"
            f"  Security:     [white]{', '.join(sg_list) or 'None'}[/white]\n"
            f"  Launched:     [white]{instance.launch_time or 'Unknown'}[/white]",
            title=f"CloudPilot - {name}",
            border_style="cyan"
        ))


class S3Manager:
    def __init__(self):
        self.s3_resource = get_s3_resource()
        self.s3_client = get_s3_client()

    def list_buckets(self):
        console.print("\nS3 Buckets\n", style="bold")

        buckets = list(self.s3_resource.buckets.all())

        if not buckets:
            console.print("  No buckets found.", style="yellow")
            return []

        table = Table(
            title="S3 Buckets",
            show_header=True,
            header_style="bold cyan",
            border_style="blue"
        )
        table.add_column("Bucket Name", style="green", width=35)
        table.add_column("Created", width=22)
        table.add_column("Access", width=12)

        for bucket in buckets:
            access = self.check_bucket_access(bucket.name)

            table.add_row(
                bucket.name,
                str(bucket.creation_date.strftime('%Y-%m-%d %H:%M')),
                access
            )

        console.print(table)
        console.print(f"\n  Total: {len(buckets)} buckets\n")
        return buckets

    def create_bucket(self, name, region=None):
        region = region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        console.print(f"\nCreating bucket '{name}'...", style="cyan")

        try:
            if region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=name)
            else:
                self.s3_client.create_bucket(
                    Bucket=name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )

            self.s3_client.put_public_access_block(
                Bucket=name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )

            console.print(f"Bucket '{name}' created (public access blocked)", style="green")
            log_action("S3_CREATE", name, region)

        except ClientError as e:
            console.print(f"Error: {e}", style="bold red")

    def upload_file(self, bucket_name, file_path):
        if not os.path.exists(file_path):
            console.print(f"File not found: {file_path}", style="red")
            return

        file_name = os.path.basename(file_path)
        console.print(f"\nUploading '{file_name}' to '{bucket_name}'...", style="cyan")

        try:
            self.s3_client.upload_file(file_path, bucket_name, file_name)
            console.print(f"Uploaded: {file_name}", style="green")
            log_action("S3_UPLOAD", bucket_name, file_name)
        except ClientError as e:
            console.print(f"Upload failed: {e}", style="bold red")

    def delete_bucket(self, name):
        if not confirm_action(f"Delete bucket '{name}' and ALL contents?"):
            console.print("Cancelled.", style="yellow")
            return

        try:
            bucket = self.s3_resource.Bucket(name)
            console.print(f"Deleting all objects in '{name}'...", style="yellow")
            bucket.objects.all().delete()
            bucket.delete()
            console.print(f"Bucket '{name}' deleted.", style="green")
            log_action("S3_DELETE", name)
        except ClientError as e:
            console.print(f"Error: {e}", style="bold red")

    def check_bucket_access(self, bucket_name):
        try:
            response = self.s3_client.get_public_access_block(Bucket=bucket_name)
            config = response['PublicAccessBlockConfiguration']
            if all([config['BlockPublicAcls'], config['IgnorePublicAcls'],
                    config['BlockPublicPolicy'], config['RestrictPublicBuckets']]):
                return "Private"
            return "PUBLIC!"
        except ClientError:
            return "Unknown"


class SecurityAuditor:
    def __init__(self):
        self.ec2_client = get_ec2_client()
        self.iam_client = get_iam_client()
        self.s3_client = get_s3_client()
        self.issues = []
        self.score = 100

    def full_scan(self):
        console.print("\nRunning Security Scan...\n", style="bold")

        with Progress() as progress:
            task = progress.add_task("[cyan]Scanning...", total=4)

            progress.update(task, description="[cyan]Checking Security Groups...")
            self.check_security_groups()
            progress.advance(task)

            progress.update(task, description="[cyan]Checking IAM Users...")
            self.check_iam_mfa()
            progress.advance(task)

            progress.update(task, description="[cyan]Checking Access Keys...")
            self.check_old_access_keys()
            progress.advance(task)

            progress.update(task, description="[cyan]Checking S3 Buckets...")
            self.check_public_s3()
            progress.advance(task)

        grade = self.calculate_grade()
        self.display_results(grade)

    def check_security_groups(self):
        try:
            sgs = self.ec2_client.describe_security_groups()
            dangerous_ports = {22: 'SSH', 3389: 'RDP', 3306: 'MySQL', 5432: 'PostgreSQL', 27017: 'MongoDB'}

            for sg in sgs['SecurityGroups']:
                for perm in sg.get('IpPermissions', []):
                    for ip_range in perm.get('IpRanges', []):
                        if ip_range.get('CidrIp') == '0.0.0.0/0':
                            port = perm.get('FromPort', 'All')
                            port_name = dangerous_ports.get(port, f'Port {port}')

                            self.issues.append({
                                'severity': 'CRITICAL' if port in [22, 3389, 3306] else 'WARNING',
                                'category': 'Security Group',
                                'message': f"{sg['GroupName']}: {port_name} (port {port}) open to 0.0.0.0/0",
                                'fix': f"Restrict port {port} to specific IPs"
                            })

                            if port in [22, 3389, 3306, 5432, 27017]:
                                self.score -= 15
                            else:
                                self.score -= 5
        except ClientError:
            pass

    def check_iam_mfa(self):
        try:
            users = self.iam_client.list_users()
            for user in users['Users']:
                mfa_devices = self.iam_client.list_mfa_devices(UserName=user['UserName'])
                if not mfa_devices['MFADevices']:
                    self.issues.append({
                        'severity': 'WARNING',
                        'category': 'IAM',
                        'message': f"User '{user['UserName']}' has NO MFA",
                        'fix': 'Enable MFA for this user'
                    })
                    self.score -= 10
        except ClientError:
            pass

    def check_old_access_keys(self):
        try:
            users = self.iam_client.list_users()
            for user in users['Users']:
                keys = self.iam_client.list_access_keys(UserName=user['UserName'])
                for key in keys['AccessKeyMetadata']:
                    age = (datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']).days
                    if age > 90:
                        self.issues.append({
                            'severity': 'WARNING',
                            'category': 'IAM',
                            'message': f"User '{user['UserName']}' key is {age} days old",
                            'fix': 'Rotate access keys every 90 days'
                        })
                        self.score -= 5
        except ClientError:
            pass

    def check_public_s3(self):
        try:
            s3 = get_s3_resource()
            for bucket in s3.buckets.all():
                try:
                    response = self.s3_client.get_public_access_block(Bucket=bucket.name)
                    config = response['PublicAccessBlockConfiguration']
                    if not all([config['BlockPublicAcls'], config['IgnorePublicAcls'],
                                config['BlockPublicPolicy'], config['RestrictPublicBuckets']]):
                        self.issues.append({
                            'severity': 'CRITICAL',
                            'category': 'S3',
                            'message': f"Bucket '{bucket.name}' may be public",
                            'fix': 'Enable public access block'
                        })
                        self.score -= 20
                except ClientError:
                    pass
        except ClientError:
            pass

    def calculate_grade(self):
        self.score = max(0, self.score)
        if self.score >= 90:
            return 'A'
        elif self.score >= 80:
            return 'B'
        elif self.score >= 70:
            return 'C'
        elif self.score >= 60:
            return 'D'
        else:
            return 'F'

    def display_results(self, grade):
        if self.score >= 80:
            score_color = "green"
        elif self.score >= 60:
            score_color = "yellow"
        else:
            score_color = "red"

        console.print(Panel.fit(
            f"\n  [bold {score_color}]Security Score: {self.score}/100 (Grade: {grade})[/bold {score_color}]\n",
            title="Security Audit Results",
            border_style=score_color
        ))

        if not self.issues:
            console.print("  No security issues found!\n", style="green")
            return

        table = Table(title=f"Issues Found: {len(self.issues)}", show_header=True, header_style="bold red")
        table.add_column("Severity", width=12)
        table.add_column("Category", width=16)
        table.add_column("Issue", width=45)
        table.add_column("Fix", width=30)

        for issue in self.issues:
            table.add_row(issue['severity'], issue['category'], issue['message'], issue['fix'])

        console.print(table)

        critical = sum(1 for i in self.issues if i['severity'] == 'CRITICAL')
        warnings = sum(1 for i in self.issues if i['severity'] == 'WARNING')
        console.print(f"\n  Summary: [red]{critical} critical[/red] | [yellow]{warnings} warnings[/yellow]\n")


class CostAnalyzer:
    def __init__(self):
        self.ec2_resource = get_ec2_resource()

    def estimate_costs(self):
        console.print("\nCost Estimation\n", style="bold")

        table = Table(title="Running Resource Costs", show_header=True, header_style="bold cyan")
        table.add_column("Resource", style="green", width=25)
        table.add_column("Type", width=15)
        table.add_column("State", width=10)
        table.add_column("Hourly", style="yellow", width=12)
        table.add_column("Monthly", style="red", width=12)

        total_monthly = 0

        for instance in self.ec2_resource.instances.all():
            name = get_instance_name(instance)
            state = instance.state['Name']

            if state == 'running':
                hourly = get_hourly_cost(instance.instance_type)
                monthly = hourly * 24 * 30
                total_monthly += monthly
                table.add_row(name, instance.instance_type, "running", f"${hourly:.4f}", f"${monthly:.2f}")
            elif state == 'stopped':
                table.add_row(name, instance.instance_type, "stopped", "$0.00", "$0.00")

        console.print(table)

        console.print(Panel.fit(
            f"  Total Estimated Cost\n\n"
            f"  Monthly: [red]${total_monthly:.2f}[/red]\n"
            f"  Yearly:  [red]${total_monthly * 12:.2f}[/red]",
            title="Cost Summary",
            border_style="yellow"
        ))

        if total_monthly == 0:
            console.print("\n  No running resources. $0 cost!\n", style="green")


class IAMManager:
    def __init__(self):
        self.iam_client = get_iam_client()

    def list_users(self):
        console.print("\nIAM Users\n", style="bold")

        try:
            users = self.iam_client.list_users()

            if not users['Users']:
                console.print("  No IAM users found.", style="yellow")
                return

            table = Table(title="IAM Users", show_header=True, header_style="bold cyan")
            table.add_column("Username", style="green", width=20)
            table.add_column("MFA", width=10, justify="center")
            table.add_column("Access Keys", width=12, justify="center")
            table.add_column("Created", width=20)

            mfa_count = 0

            for user in users['Users']:
                username = user['UserName']

                mfa_devices = self.iam_client.list_mfa_devices(UserName=username)
                has_mfa = len(mfa_devices['MFADevices']) > 0
                if has_mfa:
                    mfa_count += 1

                keys = self.iam_client.list_access_keys(UserName=username)
                key_count = len(keys['AccessKeyMetadata'])

                table.add_row(
                    username,
                    "Yes" if has_mfa else "No",
                    str(key_count),
                    user['CreateDate'].strftime('%Y-%m-%d')
                )

            console.print(table)
            total = len(users['Users'])
            console.print(f"\n  Total: {total} users | MFA: {mfa_count}/{total}\n")

        except ClientError as e:
            console.print(f"Error: {e}", style="bold red")


class Dashboard:
    def show(self):
        ec2_info = self.get_ec2_info()
        s3_info = self.get_s3_info()
        iam_info = self.get_iam_info()
        cost_info = self.get_cost_info()

        console.print(Panel.fit(
            f"\n"
            f"  EC2:       [cyan]{ec2_info['running']} running[/cyan] | "
            f"[red]{ec2_info['stopped']} stopped[/red]\n"
            f"  S3:        [cyan]{s3_info['count']} buckets[/cyan]\n"
            f"  Cost:      [red]${cost_info['monthly']:.2f}/month[/red]\n"
            f"  IAM:       [cyan]{iam_info['users']} users[/cyan] | "
            f"{iam_info['mfa']} with MFA\n"
            f"  Region:    [white]{os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}[/white]\n",
            title="CloudPilot - Dashboard",
            border_style="cyan",
            padding=(1, 2)
        ))

        console.print(f"  Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", style="dim")

    def get_ec2_info(self):
        try:
            ec2 = get_ec2_resource()
            instances = list(ec2.instances.all())
            running = sum(1 for i in instances if i.state['Name'] == 'running')
            stopped = sum(1 for i in instances if i.state['Name'] == 'stopped')
            return {'total': len(instances), 'running': running, 'stopped': stopped}
        except Exception:
            return {'total': 0, 'running': 0, 'stopped': 0}

    def get_s3_info(self):
        try:
            s3 = get_s3_resource()
            count = sum(1 for _ in s3.buckets.all())
            return {'count': count}
        except Exception:
            return {'count': 0}

    def get_iam_info(self):
        try:
            iam = get_iam_client()
            users = iam.list_users()['Users']
            mfa_count = 0
            for user in users:
                mfa = iam.list_mfa_devices(UserName=user['UserName'])
                if mfa['MFADevices']:
                    mfa_count += 1
            return {'users': len(users), 'mfa': mfa_count}
        except Exception:
            return {'users': 0, 'mfa': 0}

    def get_cost_info(self):
        try:
            ec2 = get_ec2_resource()
            monthly = 0
            for instance in ec2.instances.all():
                if instance.state['Name'] == 'running':
                    monthly += get_monthly_cost(instance.instance_type)
            return {'monthly': monthly}
        except Exception:
            return {'monthly': 0}


class CleanupManager:
    def cleanup(self):
        console.print("\nCleanup - Find Costly Resources\n", style="bold")

        resources = []
        total_cost = 0

        try:
            ec2 = get_ec2_resource()
            for instance in ec2.instances.all():
                if instance.state['Name'] in ['running', 'stopped']:
                    name = get_instance_name(instance)
                    monthly = get_monthly_cost(instance.instance_type)
                    if instance.state['Name'] == 'running':
                        total_cost += monthly
                    resources.append({
                        'type': 'EC2',
                        'name': name,
                        'id': instance.id,
                        'state': instance.state['Name'],
                        'cost': monthly if instance.state['Name'] == 'running' else 0
                    })
        except Exception:
            pass

        if not resources:
            console.print("  No costly resources found!\n", style="green")
            return

        table = Table(title="Resources Found", show_header=True, header_style="bold cyan")
        table.add_column("Type", width=10)
        table.add_column("Name", style="green", width=20)
        table.add_column("ID", style="cyan", width=22)
        table.add_column("State", width=10)
        table.add_column("Cost/Month", style="red", width=12)

        for r in resources:
            table.add_row(r['type'], r['name'], r['id'], r['state'], f"${r['cost']:.2f}")

        console.print(table)
        console.print(f"\n  Total monthly cost: [red]${total_cost:.2f}[/red]\n")

        if confirm_action("Terminate ALL resources to save money?"):
            ec2 = get_ec2_resource()
            for r in resources:
                try:
                    instance = ec2.Instance(r['id'])
                    instance.terminate()
                    console.print(f"  Terminated: {r['name']} ({r['id']})", style="red")
                except Exception as e:
                    console.print(f"  Failed: {r['name']} - {e}", style="red")

            console.print(f"\n  Cleanup complete! Saved ~${total_cost:.2f}/month\n", style="green")
        else:
            console.print("  Cancelled.\n", style="yellow")


# ============================================================
# CLI COMMANDS
# ============================================================

@click.group()
@click.version_option(version='1.0.0', prog_name='CloudPilot')
def cli():
    """CloudPilot - AWS Infrastructure Command Center"""
    pass


@cli.group()
def ec2():
    """Manage EC2 instances"""
    pass


@ec2.command('launch')
@click.option('--name', '-n', required=True, help='Instance name')
@click.option('--type', '-t', 'instance_type', default='t2.micro', help='Instance type')
@click.option('--ami', '-a', default=None, help='AMI ID')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_launch(name, instance_type, ami, region):
    """Launch a new EC2 instance"""
    manager = EC2Manager(region)
    manager.launch(name, instance_type, ami)


@ec2.command('list')
@click.option('--state', '-s', default='all', type=click.Choice(['all', 'running', 'stopped']), help='Filter by state')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_list(state, region):
    """List all EC2 instances"""
    manager = EC2Manager(region)
    manager.list_instances(state)


@ec2.command('stop')
@click.argument('identifier')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_stop(identifier, region):
    """Stop an EC2 instance (by name or ID)"""
    manager = EC2Manager(region)
    manager.stop_instance(identifier)


@ec2.command('start')
@click.argument('identifier')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_start(identifier, region):
    """Start a stopped EC2 instance"""
    manager = EC2Manager(region)
    manager.start_instance(identifier)


@ec2.command('terminate')
@click.argument('identifier', required=False)
@click.option('--all', 'terminate_all', is_flag=True, help='Terminate ALL')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_terminate(identifier, terminate_all, region):
    """Terminate an EC2 instance (IRREVERSIBLE)"""
    manager = EC2Manager(region)
    if terminate_all:
        manager.terminate_all()
    elif identifier:
        manager.terminate_instance(identifier)
    else:
        console.print("Provide instance name/ID or use --all", style="red")


@ec2.command('status')
@click.argument('identifier')
@click.option('--region', '-r', default=None, help='AWS region')
def ec2_status(identifier, region):
    """Show detailed instance status"""
    manager = EC2Manager(region)
    manager.instance_status(identifier)


@cli.group()
def s3():
    """Manage S3 buckets"""
    pass


@s3.command('list')
def s3_list():
    """List all S3 buckets"""
    manager = S3Manager()
    manager.list_buckets()


@s3.command('create')
@click.option('--name', '-n', required=True, help='Bucket name')
@click.option('--region', '-r', default=None, help='AWS region')
def s3_create(name, region):
    """Create a new S3 bucket"""
    manager = S3Manager()
    manager.create_bucket(name, region)


@s3.command('upload')
@click.option('--bucket', '-b', required=True, help='Bucket name')
@click.option('--file', '-f', 'file_path', required=True, help='File path')
def s3_upload(bucket, file_path):
    """Upload a file to S3"""
    manager = S3Manager()
    manager.upload_file(bucket, file_path)


@s3.command('delete')
@click.option('--name', '-n', required=True, help='Bucket name')
def s3_delete(name):
    """Delete an S3 bucket"""
    manager = S3Manager()
    manager.delete_bucket(name)


@cli.group()
def security():
    """Security auditing"""
    pass


@security.command('scan')
def security_scan():
    """Run full security scan"""
    auditor = SecurityAuditor()
    auditor.full_scan()


@cli.group()
def cost():
    """Cost analysis"""
    pass


@cost.command('estimate')
def cost_estimate():
    """Estimate monthly costs"""
    analyzer = CostAnalyzer()
    analyzer.estimate_costs()


@cli.group()
def iam():
    """IAM user management"""
    pass


@iam.command('users')
def iam_users():
    """List all IAM users"""
    manager = IAMManager()
    manager.list_users()


@cli.command()
def overview():
    """Show infrastructure dashboard"""
    dashboard = Dashboard()
    dashboard.show()


@cli.command()
def cleanup():
    """Find and remove costly resources"""
    manager = CleanupManager()
    manager.cleanup()


if __name__ == '__main__':
    cli()  