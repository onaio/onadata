## Required

- pip install -r requirements.txt
- Edit email, aws_email, and replace AWS_*, SITE_DOMAIN, ALERT_RECIPIENTS with correct details for your server setup.

# Deploy

    $ fab deploy:prod,scripts='system email aws_email, nginx postgres rabbitmq'

