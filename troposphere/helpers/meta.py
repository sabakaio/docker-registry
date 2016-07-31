from os.path import dirname, join
from troposphere import Ref, Base64, Join
from troposphere import cloudformation as cf, ec2, autoscaling as au


def docker():
    return cf.InitConfig(
        'Docker',
        packages={'yum': {'docker': []}},
        commands={
            'docker_user': {
                'command': 'usermod -aG docker ec2-user'
            },
            'install_compose': {
                'command': 'pip install docker-compose'
            },
        },
        services={
            'sysvinit': {
                'docker': {
                    'enabled': True,
                    'ensureRunning': True
                }
            }
        }
    )


def registry(certs_dir, bucket):
    certs_dir = certs_dir.rstrip('/')
    compose_file = '/opt/registry/docker-compose.yml'
    compose_tpl = compose_file + '.template'
    project_dir = dirname(dirname(dirname(__file__)))
    with open(join(project_dir, 'docker-compose.yml')) as f:
        compose_yml = Join('', list(f.readlines()))

    with open(join(project_dir, 'proxy', 'nginx.conf')) as f:
        nginx_conf = Join('', list(f.readlines()))
    with open(join(project_dir, 'proxy', 'registry.conf')) as f:
        nginx_registry_conf = Join('', list(f.readlines()))

    return cf.InitConfig(
        'Registry',
        packages={'yum': {'openssl': [], 'gettext': []}},
        files={
            compose_tpl: {
                'content': compose_yml,
                'mode': '000664',
                'owner': 'root',
                'group': 'docker',
            },
            join(dirname(compose_file), 'nginx.conf'): {
                'content': nginx_conf,
                'mode': '000664',
                'owner': 'root',
                'group': 'root',
            },
            join(dirname(compose_file), 'registry.conf'): {
                'content': nginx_registry_conf,
                'mode': '000664',
                'owner': 'root',
                'group': 'root',
            },
        },
        commands={
            '1_make_compose': {
                'command': 'envsubst < {t} > {f}'.format(t=compose_tpl, f=compose_file),
                'env': {
                    'AWS_REGION': Ref('AWS::Region'),
                    'STORAGE_BUCKET': Ref(bucket),
                    'CERTS_DIR': certs_dir,
                }
            },
            '2_gen_dh': {
                'command': 'openssl dhparam -out {d}/dh.pem 2048'.format(d=certs_dir)
            },
            '3_up': {
                'command': '/usr/local/bin/docker-compose -f {f} up -d'.format(f=compose_file)
            },
        }
    )


def certbot(domain, email, conf_dir='/opt/certs/', copy_to=None):
    script_name = '/opt/certbot-auto'
    commands = {
        '1_get_cert': {
            'command': Join(' ', [
                script_name, 'certonly',
                '--config-dir', conf_dir,
                '--standalone --debug --agree-tos --non-interactive',
                '-d', domain,
                '--email', email,
            ])
        }
    }
    if copy_to:
        commands.update({
            '2_certs_dest': {
                'command': 'mkdir -p ' + copy_to,
            },
            '3_copy_certs': {
                'cwd': copy_to,
                'command': Join('', [
                    'cp ' + conf_dir.rstrip('/') + '/live/', domain, '/*.pem .'
                ])
            },
        })
    return cf.InitConfig(
        'Certbot',
        files={
            script_name: {
                'source': 'https://dl.eff.org/certbot-auto',
                'mode': '000755',
                'owner': 'root',
                'group': 'root',
            },
            '/etc/cron.daily/certbot_renew': {
                'content': Join('', [
                    '#/bin/bash -e\n',
                    script_name + ' renew --config-dir ' + conf_dir,
                ]),
                'mode': '000755',
                'owner': 'root',
                'group': 'root',
            },
        },
        commands=commands
    )


def add_init(target, *configs):
    assert isinstance(target, (ec2.Instance, au.LaunchConfiguration))
    params = Join('', [
        'export CFN_PARAMS=\'',
        ' --region ', Ref('AWS::Region'),
        ' --stack ', Ref('AWS::StackName'),
        ' --resource ' + target.title + '\'',
    ])
    target.UserData = Base64(Join('\n', [
        '#!/bin/bash -xe',
        'yum update -y',
        params,
        '/opt/aws/bin/cfn-init -v -c default $CFN_PARAMS',
        '/opt/aws/bin/cfn-signal -e 0 $CFN_PARAMS'
    ]))

    configs = [callable(c) and c() or c for c in configs]
    target.Metadata = cf.Init(
        cf.InitConfigSets(default=[c.title for c in configs]),
        **{c.title: c for c in configs})
    return target
