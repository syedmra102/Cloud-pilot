# ☁️ CloudPilot — AWS Infrastructure Command Center

A comprehensive CLI tool to manage, secure, and monitor your entire AWS infrastructure from the terminal.

Built with Python, boto3, and Rich for beautiful terminal output.

## 🎯 What is CloudPilot?

CloudPilot is an all-in-one AWS management tool that lets you:

- **Manage EC2** — Launch, list, stop, start, terminate instances
- **Manage S3** — Create, list, upload, delete buckets
- **Security Audit** — Scan for vulnerabilities, get security score
- **Cost Analysis** — Estimate monthly costs, find savings
- **IAM Management** — List users, check MFA status
- **Dashboard** — Complete infrastructure overview
- **Cleanup** — Find and remove costly unused resources

## 📸 Screenshots

### Dashboard Overview
![Dashboard](C:\Users\LENOVO\Pictures\Screenshots\Screenshot 2026-04-02 101337.png)

### EC2 Instance Management
![EC2 List]("C:\Users\LENOVO\Pictures\Screenshots\Screenshot 2026-04-02 103322.png")

### Launch New Instance
![EC2 Launch]("C:\Users\LENOVO\Pictures\Screenshots\Screenshot 2026-04-02 103350.png")

### Security Scan
![Security Scan]("C:\Users\LENOVO\Pictures\Screenshots\Screenshot 2026-04-02 103517.png")

### Cost Estimation
![Cost Estimate]()"C:\Users\LENOVO\Pictures\Screenshots\Screenshot 2026-04-02 103537.png"

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS Account with access keys
- AWS CLI configured

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/cloudpilot.git
cd cloudpilot

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your AWS credentials

## CONFIGRATION

# Option 1: Use .env file
cp .env.example .env
# Edit .env and add your AWS credentials

# Option 2: Use AWS CLI
aws configure
# Enter your Access Key, Secret Key, and Region


📖 Usage
#Dashboard — See Everything at a Glance

python cloudpilot.py overview

EC2 Instance Management


# List all instances
python cloudpilot.py ec2 list

# List only running instances
python cloudpilot.py ec2 list --state running

# Launch new instance
python cloudpilot.py ec2 launch --name "my-server" --type t3.micro

# Check instance status
python cloudpilot.py ec2 status my-server

# Stop instance
python cloudpilot.py ec2 stop my-server

# Start stopped instance
python cloudpilot.py ec2 start my-server

# Terminate instance (permanent!)
python cloudpilot.py ec2 terminate my-server

# Terminate ALL instances
python cloudpilot.py ec2 terminate --all
S3 Bucket Management
Bash

# List all buckets
python cloudpilot.py s3 list

# Create new bucket
python cloudpilot.py s3 create --name "my-bucket-name-12345"

# Upload file to bucket
python cloudpilot.py s3 upload --bucket "my-bucket" --file ./data.txt

# Delete bucket
python cloudpilot.py s3 delete --name "my-bucket-name-12345"
Security Auditing


# Run full security scan
python cloudpilot.py security scan
The security scanner checks:

Security Groups for overly permissive rules (0.0.0.0/0)
IAM users without MFA enabled
Access keys older than 90 days
S3 buckets with public access
Each scan produces a security score (A-F grade).

Cost Analysis


# Estimate monthly costs
python cloudpilot.py cost estimate
IAM User Management
Bash

# List all IAM users with MFA status
python cloudpilot.py iam users
Cleanup Resources


# Find and remove costly resources
python cloudpilot.py cleanup


🛠️ Built With
Technology	Purpose
Python 3	Core programming language
boto3	AWS SDK for Python
Click	CLI framework for commands
Rich	Beautiful terminal formatting
python-dotenv	Environment variable management
📁 Project Structure


cloudpilot/
├── cloudpilot.py          # Main application (all classes and CLI)
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment variables
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── screenshots/          # Application screenshots
🔒 Security Features
Secret Protection — AWS credentials stored in .env (never committed to Git)
Confirmation Prompts — All destructive actions require explicit confirmation
Security Scanning — Automated checks for common AWS misconfigurations
Action Logging — All actions logged to cloudpilot.log (excluded from Git)
Input Validation — All user inputs validated before processing
⚙️ Architecture


CloudPilot
├── Helper Functions (shared utilities)
│   ├── get_session()           — AWS connection
│   ├── get_instance_name()     — Extract Name tag
│   ├── get_state_emoji()       — Status indicators
│   ├── get_hourly_cost()       — Cost calculations
│   ├── confirm_action()        — Safety confirmations
│   └── log_action()            — Activity logging
│
├── EC2Manager (server management)
│   ├── launch()                — Create instances
│   ├── list_instances()        — Show all instances
│   ├── find_instance()         — Search by name/ID
│   ├── stop_instance()         — Stop running instance
│   ├── start_instance()        — Start stopped instance
│   ├── terminate_instance()    — Delete instance
│   ├── terminate_all()         — Delete all instances
│   └── instance_status()       — Detailed instance info
│
├── S3Manager (storage management)
│   ├── list_buckets()          — Show all buckets
│   ├── create_bucket()         — Create new bucket
│   ├── upload_file()           — Upload to bucket
│   └── delete_bucket()         — Delete bucket
│
├── SecurityAuditor (security scanning)
│   ├── full_scan()             — Complete security audit
│   ├── check_security_groups() — Firewall rule check
│   ├── check_iam_mfa()         — MFA status check
│   ├── check_old_access_keys() — Key rotation check
│   └── check_public_s3()       — Public bucket check
│
├── CostAnalyzer (cost management)
│   └── estimate_costs()        — Monthly cost breakdown
│
├── IAMManager (user management)
│   └── list_users()            — User listing with MFA
│
├── Dashboard (overview)
│   └── show()                  — Infrastructure summary
│
└── CleanupManager (resource cleanup)
    └── cleanup()               — Find/remove unused resources
⚠️ Important Notes
Free Tier: Use t3.micro or t2.micro instance types to stay within AWS free tier
Costs: Always terminate instances when not in use to avoid charges
Credentials: Never share your AWS access keys or commit them to Git
Region: Make sure your .env region matches where you want to deploy


📝 License
This project is licensed under the MIT License.

👨‍💻 Author
[Syed Imran Shah]

Learning Platform Engineering, DevSecOps, and Cloud Infrastructure
Building tools to automate AWS management
Currently pursuing AWS certifications



🙏 Acknowledgments
AWS Documentation
Python boto3 Library
Rich Library for terminal formatting
Click Library for CLI framework
text


