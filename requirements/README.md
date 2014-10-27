#REQUIREMENTS

- ***base.pip*** - Contains requirements common to all environs and deploys.  
- ***dev.pip*** - Requirements used for development and testing.  
- ***latest.pip*** - Requirements file with the "latest possible" package versions.
Used only to test compatibility with latest version of dependencies.  
- ***mysql.pip*** - Legacy. previously used to deploy with mysql as opposed to postgre.  

- ***s3.pip*** - AWS S3 requirements used mainly in production.  
- ***ses.pip*** - SES Mail backend requirements.  
