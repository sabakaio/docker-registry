# Docker Registry

Docker Registry AWS setup automation.

## Installation

- Create *Elastic IP* and add DNS record to this IP. We need this configured to issue sertificates using *LetsEncrypt*.
- Create a DNS record for the Registry to point to *Elastic IP* created in previous step
- Generate *CloudFormation* template using *troposphere* `python troposphere/registry.py > registry.template`
- Create a *CloudFormation Stack* using `registry.template`
- Go to registry instance `ssh ec2-user@<your.registry>`
- Add user `docker run --entrypoint htpasswd registry:2 -Bbn my_user my_password > /opt/registry/htpasswd`
- Restart the registry `cd /opt/registry && /usr/local/bin/docker-compose up -d --force-recreate`

## TODO

- Copy certs after renewal and restart Registry
- CloudFormation wait condition for registry instance
