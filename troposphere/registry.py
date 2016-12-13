from functools import partial

from troposphere import Output, Parameter, Template
from troposphere import GetAtt, Ref, Join
from troposphere import constants as c, ec2, s3

from helpers import iam
from helpers import meta
from helpers.amilookup.resources import ami_lookup

template = Template()

az = template.add_parameter(Parameter(
    'AvailabilityZone',
    Type=c.AVAILABILITY_ZONE_NAME,
    Description='Availability Zone of the Subnet'
))
ssh_key = template.add_parameter(Parameter(
    'SSHKeyName',
    Type=c.KEY_PAIR_NAME,
    Description='Name of an existing EC2 KeyPair to enable SSH access to the instance'
))
ssh_location = template.add_parameter(Parameter(
    'SSHLocation',
    Description='The IP address range that can be used to SSH to the EC2 instances',
    Type=c.STRING,
    MinLength='9',
    MaxLength='18',
    Default='0.0.0.0/0',
    AllowedPattern='(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})\\.(\\d{1,3})/(\\d{1,2})',
    ConstraintDescription='must be a valid IP CIDR range of the form x.x.x.x/x.'
))

ami_id = GetAtt(ami_lookup(template), 'Id')

ssh_sg = ec2.SecurityGroup(
    'SSHSecurityGroup', template,
    SecurityGroupIngress=[
        {'IpProtocol': 'tcp', 'FromPort': '22', 'ToPort': '22', 'CidrIp': Ref(ssh_location)}
    ],
    GroupDescription='Enable SSH on port 22 for given location'
)
web_sg = ec2.SecurityGroup(
    'WebSecurityGroup', template,
    SecurityGroupIngress=[
        {'IpProtocol': 'tcp', 'FromPort': '443', 'ToPort': '443', 'CidrIp': '0.0.0.0/0'},
    ],
    GroupDescription='Enable HTTPS ports for all incoming traffic'
)

service_name = 'DockerRegistry'

bucket = template.add_resource(s3.Bucket(
    service_name + 'Storage',
    AccessControl=s3.Private,
))

registry_profile = iam.make_instance_profile(
    service_name + 'InstanceProfile', template,
    partial(iam.bucket_full_access, bucket)
)

registry_instance_type = template.add_parameter(Parameter(
    service_name + 'InstanceType',
    Type=c.STRING,
    Default=c.T2_MICRO,
    AllowedValues=[c.T2_MICRO, c.T2_SMALL, c.T2_MEDIUM, c.M4_LARGE, c.C4_LARGE]
))

registry_block_device_size = template.add_parameter(Parameter(
    service_name + 'BlockDeviseSize',
    Type=c.STRING,
    Default='30',
    Description='{n} root file system size (GB)'.format(n=service_name)
))

registry = ec2.Instance(
    service_name + 'Instance', template,
    AvailabilityZone=Ref(az),
    IamInstanceProfile=Ref(registry_profile),
    InstanceType=Ref(registry_instance_type),
    ImageId=ami_id,
    KeyName=Ref(ssh_key),
    SecurityGroupIds=[Ref(ssh_sg), Ref(web_sg)],
    BlockDeviceMappings=[ec2.BlockDeviceMapping(
        DeviceName='/dev/xvda',
        Ebs=ec2.EBSBlockDevice(
            VolumeSize=Ref(registry_block_device_size),
            VolumeType='gp2'
        )
    )],
    Tags=[ec2.Tag('Name', 'docker-registry')],
)


registry_domain = template.add_parameter(Parameter(
    'DockerRegistryCertDomainName',
    Type=c.STRING,
    Description='Domain to issue certificate for'
))
registry_domain_email = template.add_parameter(Parameter(
    'DockerRegistryCertEmail',
    Type=c.STRING,
    Description='Email to use on certificate issue'
))

registry_certs = '/opt/registry/security/'
registry_htpasswd = '/opt/registry/htpasswd'
registry_compose = Join('', [
    'version: "2"\n',
    'services:\n',
    '  registry:\n',
    '    restart: always\n',
    '    image: registry:2\n',
    '    container_name: registry\n',
    '    ports:\n',
    '      - 443:5000\n',
    '    environment:\n',
    '      REGISTRY_STORAGE: s3\n',
    '      REGISTRY_STORAGE_S3_REGION: ', Ref('AWS::Region'), '\n',
    '      REGISTRY_STORAGE_S3_ACCESSKEY: ""\n',
    '      REGISTRY_STORAGE_S3_SECRETKEY: ""\n',
    '      REGISTRY_STORAGE_S3_BUCKET: ', Ref(bucket), '\n',
    '      REGISTRY_HTTP_TLS_CERTIFICATE: /certs/fullchain.pem\n',
    '      REGISTRY_HTTP_TLS_KEY: /certs/privkey.pem\n',
    '      REGISTRY_AUTH: htpasswd\n',
    '      REGISTRY_AUTH_HTPASSWD_REALM: "Registry Realm"\n',
    '      REGISTRY_AUTH_HTPASSWD_PATH: /auth/htpasswd\n',
    '    volumes:\n',
    '      - {d}:/certs:ro\n'.format(d=registry_certs),
    '      - {f}:/auth/htpasswd\n'.format(f=registry_htpasswd),
])
compose_init, compose_file = meta.docker_compose('registry', registry_compose)

compose = '{b} -f {f}'.format(
    b='/usr/local/bin/docker-compose',
    f=compose_file)
certbot_init = meta.certbot(
    Ref(registry_domain),
    Ref(registry_domain_email),
    copy_to=registry_certs,
    pre_hook=('%s stop' % compose),
    post_hook=('%s up -d' % compose),
)

meta.add_init(
    registry,
    meta.docker,
    certbot_init,
    meta.htpasswd(registry_htpasswd),
    compose_init,
)

eip = template.add_parameter(Parameter(
    'DockerRegistryEIP',
    Type=c.STRING,
    Description=(
        'Allocation ID for the VPC Elastic IP address you want to associate '
        'with Docker Registry instance. You should already have domain name '
        'configured for this IP'
    )
))
ec2.EIPAssociation(
    service_name + 'EIPAccociation', template,
    AllocationId=Ref(eip),
    InstanceId=Ref(registry),
)

template.add_output(Output(
    registry.title + 'Ip',
    Value=GetAtt(registry, 'PublicIp')
))

print(template.to_json())
