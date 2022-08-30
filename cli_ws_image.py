#!/usr/bin/env python

"""
Avoid using list() to convert a python object to a list because we re-defined list().
If needed, use list_builtin() instead.
"""

import click
import sys
import os
import urllib
import requests
import subprocess
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import pandas as pd # to format tables
pd.options.display.width = 0

import ssl
ssl._create_default_https_context = ssl._create_unverified_context # fixed ssl certificate issue when downloading html in pandas

USER_ACCESS_TOKEN = os.getenv('USER_ACCESS_TOKEN')
USERNAME = os.getenv('USERNAME')
APIKEY = os.getenv('APIKEY')

BASE_URL = os.getenv('BASE_URL',os.getenv('RUNTIME_ENV_APSX_URL'))

HEADERS_GET = {'authorization':'Bearer {access_token}'}

VERSION = '1.1'

list_builtin = list

@click.group()
def cli():
    pass

@cli.command()
def version():
    click.echo(f"Current version: {color(VERSION)}")


# -------- cli group: default --------
@cli.group()
def default():
    """
    default WS configs
    """
    pass


@default.command()
@click.option('--cpu',is_flag=True,help='whether to display WS non-gpu default config')
@click.option('--gpu',is_flag=True,help='whether to display WS gpu default config')
@click.option('-a',is_flag=True,help='whether to display both gpu and non-gpu default config')
@click.option('--rstudio',is_flag=True,help='whether to pull information for rstudio; this overwrites these flags: --cpu, --gpu, -a')
@click.option('--service',type=str,default='ws',help='the service to list the base mage for; currently supports either ws or wml')
@click.option('--export-fn',type=str,default=None,help='the output filename')
@click.option('--export-format',type=str,default='txt',help='txt exports only the base images to be used later')
@click.option('--cpd-version','-v',type=str,default=None,help='a specific CPD version; if not specified, information of the latest version is pulled')
@click.option('--overwrite','-o',is_flag=True,help='whether to overwrite the output file if it exists')
def list(cpu,gpu,a,rstudio,service,export_fn,export_format,cpd_version,overwrite):
    """
    Stage model files, dependency files for deployment, and yml config file into the target WML space.
    """
    if service not in ['ws','wml']:
        click.echo(f"{color('Error','error')}: The value for argument {color('service','error')} should be one of ['ws', 'wml'].")
        sys.exit(1)
        
    if service == 'wml':
        cpu = True # wml service
        if gpu or a:
            click.echo(f"{color('Error','error')}: Service {color('wml','error')} supports python cpu environments for online & batch deployments (which yield a REST API), where only CPU inference is allowed. As a result you cannot specify \"--gpu\" or \"--all\". \nIf you intend to run GPU inference through a notebook/script job deployment in WML space, the underlying environments and all the steps are the same as WS environments, as in this case WML space leverages WS runtimes, so please use \"--service ws\" instead.")
            sys.exit(1)
        df_runtime = download_reference(cpd_version,service)
        df_runtime['image'] = 'cp.icr.io/cp/cpd/' + df_runtime['Image name|base-image-name'] + ':' + df_runtime['Image version|base-image-version']
        print(df_runtime)

        if export_fn is not None:
            if export_format == 'txt':
                
                images = df_runtime['image'].values.tolist()
                
                if os.path.exists(export_fn):
                    click.echo(f"Export filename {color(export_fn)} already exists.")
                    if not overwrite:
                        click.echo(f"{color('Stopped','error')}")
                        sys.exit(1)
                    else:
                        click.echo(f"Overwriting file {color(export_fn)}...")
                else:
                    click.echo(f"Export filename {color(export_fn)} does not exist.")
                
                with open(export_fn,'w') as f:
                    f.write('\n'.join(images))
                    f.write('\n') # the file needs to end with a new line character for IFS read to get the last element
                click.echo(f"Base image list written to {color(export_fn,'pass')}")

    elif service == 'ws':
        if not cpu and not gpu and not a and not rstudio:
            click.echo(f"{color('Error','error')}: Specify at least one flag for runtime type (--cpu, --gpu, -a, --rstudio).")
            sys.exit(1)
        
        if rstudio:
            if service == 'ws':
                if cpu or gpu or a:
                    click.echo(f"Flag {color('rstudio')} overrides the other flags for python environments (--cpu, --gpu, --all). Only Rstudio runtimes will be listed.")
                df_runtime = download_reference(cpd_version,service,rstudio=True)
            else:
                click.echo(f"{color('Error','error')}: {color(service,'error')} service does not have {color('rstudio','error')} environments.")
                sys.exit(1)
        else:
            cpu_only = True if (cpu and not gpu) and (not a) else False
            gpu_only = True if (gpu and not cpu) and (not a) else False
            
            if gpu_only and service != 'ws':
                click.echo(f"{color('Error','error')}: {color(service,'error')} service does not have {color('rstudio','error')} environments.")
                sys.exit(1)

            df_runtime = download_reference(cpd_version,service)
            df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-py')]
            
            if cpu_only:
                df_runtime = df_runtime[~df_runtime['JSON configuration file'].str.contains('gpu')].reset_index(drop=True)
            elif gpu_only:
                df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('gpu')].reset_index(drop=True)
            print(df_runtime)
        
        click.echo(f"\nFetching config files on CPD {color(BASE_URL)}...")
        fns = df_runtime['JSON configuration file'].tolist()
        
        d_config = get_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
        
        if len(d_config) == 0:
            click.echo(f"\nNo config file. Cannot output base image list.")
            sys.exit(1)
                    
        df = pd.DataFrame({'filename':d_config.keys(),
                        'image':[config['image'] for config in d_config.values()]})
        
        click.echo(f'\nWS config files on CPD {color(BASE_URL)}, selected fields:')
        print(df)
        
        if export_fn is not None:
            if export_format == 'txt':
                images = [config['image'] for config in d_config.values()]
                images = list_builtin(set(images))
                
                if os.path.exists(export_fn):
                    click.echo(f"Export filename {color(export_fn)} already exists.")
                    if not overwrite:
                        click.echo(f"{color('Stopped','error')}")
                        sys.exit(1)
                    else:
                        click.echo(f"Overwriting file {color(export_fn)}...")
                else:
                    click.echo(f"Export filename {color(export_fn)} does not exist.")
                
                with open(export_fn,'w') as f:
                    f.write('\n'.join(images))
                    f.write('\n') # the file needs to end with a new line character for IFS read to get the last element
                click.echo(f"Base image list written to {color(export_fn,'pass')}")

# -------- cli group: custom --------
@cli.group()
def custom():
    """
    custom WS configs
    """
    pass


@custom.command()
@click.option('--pattern','-p','-c',type=str,default='ws-applications-{filename}',help='config file name pattern, where the original config filename which the custom file is based on indicates in {filename}')
@click.option('--cpd-version','-v',type=str,default=None,help='a specific CPD version; if not specified, information of the latest version is pulled')
def list(pattern,cpd_version):
    """
    List custom runtime configurations with known name patterns
    """
    df_runtime = download_reference(cpd_version)
    print(df_runtime)
    df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-py')]
    fns = df_runtime['JSON configuration file'].tolist()
    fns_custom = [pattern.format(filename=fn) for fn in fns]
    
    d_config = get_config_files(fns_custom,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
    
    if len(d_config) == 0:
        click.echo(f"\nNo custom config file with pattern {color(pattern)}.")
        sys.exit(1)
                
    df = pd.DataFrame({'filename':d_config.keys(),
                       'image':[config['image'] for config in d_config.values()]})
    
    click.echo(f'\nWS custom config files on CPD {color(BASE_URL)} with pattern {color(pattern)}, selected fields:')
    print(df)

@custom.command()
@click.option('--name',type=str,required=True,help='config file name to fetch and view')
@click.option('--image-name',is_flag=True,help='extract information: image name')
def view(name, image_name):
    """
    View custom runtime configurations given a configuration file name. To know what configuration file names
    are available, run the `list` command first.
    """
    res = get_config_files([name],BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
    if len(res) == 1:
        res = res[name]
        if image_name:
            click.echo(f"{color('image name:')} {res['image']}")
        else:
            click.echo(f"{color('full json content:')}")
            print(res)
    

@custom.command()
@click.option('--registry-url',type=str,default='us.icr.io',help='registry url to store the custom image')
@click.option('--registry-namespace',type=str,default='custom-image',help='registry namespace to store the custom image')
@click.option('--dir-dockerfile',type=str,default='.',help='directory to the location of the dockerfile')
@click.option('--base-image-list',type=str,required=True,help='a filename of a text file containing base image names, one at a line')
@click.option('--custom-image-name-pattern',type=str,default='{image_name}-custom',help='pattern of the custom image name; where the original image name which the custom file is based on is referred to as {image_name}')
def build(registry_url, registry_namespace, dir_dockerfile, base_image_list, custom_image_name_pattern):
    """
    Build and push the custom image. 
    Note that you may need to run "docker login cp.icr.io" first, to make sure you have configured access to the
    image registry of CPD, from where to download the base image.
    """

    with open(base_image_list) as f:
        l_base_image = [base_image.replace('\n','') for base_image in f.readlines()]

    os.chdir(dir_dockerfile)
    print('Changed working directory to',dir_dockerfile)

    for base_image in l_base_image:
        if '@' in base_image:
            image_name = base_image.split('@')[0].split('/')[-1] # ws uses @
        elif ':' in base_image:
            image_name = base_image.split(':')[0].split('/')[-1] # wml uses :
        else:
            image_name = base_image
        image_name_custom = custom_image_name_pattern.format(image_name=image_name)
        print(f'Building custom image {image_name_custom} based on {image_name}')
        
        cmd = f'docker build {dir_dockerfile} --build-arg base_image_tag={base_image} -t {image_name_custom}'
        print(f'Executing command: {cmd}')
        res = subprocess.run(cmd,shell=True)
        if res.returncode != 0:
            click.echo(f"{color('FAILED','error')}: return code {res.returncode}. {res}")
        else:
            cmd = f'docker tag {image_name_custom} {registry_url}/{registry_namespace}/{image_name_custom}'
            print(f'Executing command: {cmd}')
            subprocess.run(cmd,shell=True)
            
            cmd = f'docker push {registry_url}/{registry_namespace}/{image_name_custom}'
            print(f'Executing command: {cmd}')
            subprocess.run(cmd,shell=True)
            
            print(f'Finished building custom image {image_name_custom}')



@custom.command()
@click.option('--gpu',is_flag=True,help='whether to create WS gpu runtime config')
@click.option('--jupyter',is_flag=True,help='whether to create WS jupyter notebook runtime config')
@click.option('--jupyterlab',is_flag=True,help='whether to create WS jupyterlab runtime config')
@click.option('--jupyter-all',is_flag=True,help='whether to create WS jupyterlab AND jupyterlab runtime configs, equivalent to --jupyter --jupyterlab')
@click.option('--rstudio',is_flag=True,help='whether to create custom rstudio env; this overwrites these flags: --gpu, --jupyter, --jupyterlab, --jupyter-all')
@click.option('--python-version','-py',type=str,default=None,help='a specific python version as basis; if not specified, custom config will be generated for all available WS python versions')
@click.option('--service',type=str,default='ws',help='the service to list the base mage for; currently supports either ws or wml')
@click.option('--storage-volume',type=str,default='cc-home-pvc',help='the storage volume display name for WML software specification, which mounts an existing pvc called cc-home-pvc')
@click.option('--config-filename-pattern','-c',type=str,default='custom-{filename}',help='config file name pattern, where the original config filename which the custom file is based on is referred to as {filename}; default value: custom-{filename}')
@click.option('--display-name-pattern','-d',type=str,default='{display_name} (custom)',help='display name pattern, where the original display name which the custom file is based on is referred to as {display_name}; default value: {display_name} (custom)')
@click.option('--image-name-pattern','-i',type=str,default='us.icr.io/custom-image/{image_name}-custom:2',help='image name pattern, where the original image name which the custom file is based on is referred to as {image_name}; default value: us.icr.io/custom-image/{image_name}-custom:2')
@click.option('--cpd-version','-v',type=str,default=None,help='a specific CPD version used to pull the default config list from doc; if not specified, information of the latest version is pulled')
@click.option('--dry-run',is_flag=True,help='performing all the steps except for the last step to register the new custom config in WS')
def register(gpu,jupyter,jupyterlab,jupyter_all,rstudio,python_version,service,
           config_filename_pattern,display_name_pattern,image_name_pattern,cpd_version,dry_run):
    """
    List custom runtime configurations with known name patterns.
    For WS environments, you may specify flags such as gpu, jupyter, jupyterlab, jupyter_all, or rstudio.
    For WML environments, the above flags do not apply, as it only supports python cpu runtimes with no jupyter or jupyterlab.
    """
    if service not in ['ws','wml']:
        click.echo(f"{color('Error','error')}: The value for argument {color('service','error')} should be one of ['ws', 'wml'].")
        sys.exit(1)
        
    if service == 'wml':
        if gpu or jupyter or jupyterlab or jupyter_all or rstudio:
            click.echo(f"{color('Error','error')}: Service {color('wml','error')} supports python cpu environments for online & batch deployments (which yield a REST API), where only CPU inference is allowed. As a result you cannot specify flags such as \"--gpu\" or \"--rstudio\". \nIf you intend to run GPU inference through a notebook/script job deployment in WML space, the underlying environments and all the steps are the same as WS environments, as in this case WML space leverages WS runtimes, so please use \"--service ws\" instead.")
            sys.exit(1)
        
        df_runtime = download_reference(cpd_version,service)
        df_runtime['image'] = 'cp.icr.io/cp/cpd/' + df_runtime['Image name|base-image-name'] + ':' + df_runtime['Image version|base-image-version']
        print(df_runtime)
    else:
        if not jupyter and not jupyterlab and not jupyter_all and not rstudio:
            click.echo(f"{color('Error','error')}: Specify at least one flag (--jupyter, --jupyterlab, --jupyter-all, --rstudio).")
            sys.exit(1)
        
        if rstudio:
            # 1. download default config names from doc
            df_runtime = download_reference(cpd_version,rstudio=True)
        else:
            jupyter_only = True if (jupyter and not jupyterlab) and (not jupyter_all) else False
            jupyterlab_only = True if (jupyterlab and not jupyter) and (not jupyter_all) else False
            
            # 1. download default config names from doc
            df_runtime = download_reference(cpd_version)
            df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-py')]
            
            if not gpu:
                df_runtime = df_runtime[~df_runtime['JSON configuration file'].str.contains('gpu')].reset_index(drop=True)
            else:
                df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('gpu')].reset_index(drop=True)
            
            if jupyter_only:
                df_runtime = df_runtime[~df_runtime['JSON configuration file'].str.contains('-lab-')].reset_index(drop=True)
            elif jupyterlab_only:
                df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-lab-')].reset_index(drop=True)
            
            if python_version:
                df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains(f'-py{python_version.replace(".","")}')].reset_index(drop=True)
            
            if df_runtime.shape[0] > 0:
                print(df_runtime)
            else:
                click.echo(f"{color('Cannot find matching default runtime config to start with.','error')}")
                sys.exit(1)
        
        # 2. according to names, fetch the default config files from the cluster
        click.echo(f"\nFetching default config files on CPD {color(BASE_URL)}...")
        fns = df_runtime['JSON configuration file'].tolist()
        
        d_config = get_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
        
        if len(d_config) == 0:
            click.echo(f"\nNo matching default config file on cluster {color(BASE_URL)}. Cannot proceed.")
            sys.exit(1)
                    
        df = pd.DataFrame({'filename':d_config.keys(),
                        'image':[config['image'] for config in d_config.values()]})
        print(df)
        
        # 3. modify the default config to create a custom one
        d_config_new = {}
        for fn,config in d_config.items():
            try:
                fn_new = config_filename_pattern.format(filename=fn)

                image_name = config['image'].split('@')[0].split('/')[-1]
                image_name_new = image_name_pattern.format(image_name=image_name)
                config['image'] = image_name_new

                if rstudio:
                    display_name = config['display_name']
                    display_name_new = display_name_pattern.format(display_name=display_name)
                    config['display_name'] = display_name_new
                else:
                    display_name = config['displayName']
                    display_name_new = display_name_pattern.format(display_name=display_name)
                    config['displayName'] = display_name_new

                d_config_new[fn_new] = config

            except Exception as e:
                click.echo(f"{color('Error','error')}: {e}")
        
        # 4. write te custom config files to disk
        os.makedirs('./tmp',exist_ok=True)
        for fn,config in d_config_new.items():
            with open(f'./tmp/{fn}','w') as f:
                print("Writing new config to file ./tmp/" + fn)
                json.dump(config, f)
        
        # 5. register the custom config file to WS
        if dry_run:
            click.echo('Dry run is finished. You can check the generated custom config files.')
            sys.exit(0)
        else:
            put_config_files(['./tmp/'+fn for fn in d_config_new.keys()], BASE_URL, USERNAME, APIKEY, USER_ACCESS_TOKEN, HEADERS_GET)
        
# -------- util --------

def color(x,condition='normal'):
    if condition=='normal':
        return click.style(str(x),fg='blue')
    elif condition=='error':
        return click.style(str(x),fg='red')
    elif condition=='warning':
        return click.style(str(x),fg='yellow')
    elif condition=='pass':
        return click.style(str(x),fg='green')
    else:
        raise Exception(f'condition {condition} not supported')
        
AUTHENTICATE = '/icp4d-api/v1/authorize'
HEADERS_AUTH = {'Content-Type':'application/json'}

def get_access_token(credentials, host_url=BASE_URL):
    """
    Authenticate using api key and get CPD access token for API authorization.
    
    credentials: a dictionary with key "username" and "api_key"
    """
    requests_args = {'url': host_url+AUTHENTICATE,
                     'headers': HEADERS_AUTH,
                     'json': credentials,
                     'verify': False}
    
    out = requests.post(**requests_args)
    return out.json()['token']


def validate_authorization(BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN):
    BASE_URL = None if BASE_URL is not None and len(BASE_URL) < 10 else BASE_URL
    USERNAME = None if USERNAME is not None and USERNAME == '' else USERNAME
    APIKEY = None if APIKEY is not None and len(APIKEY) < 35 else APIKEY
    USER_ACCESS_TOKEN = None if USER_ACCESS_TOKEN is not None and len(USER_ACCESS_TOKEN) < 1000 else USER_ACCESS_TOKEN
    
    if BASE_URL is None:
        click.echo(f"{color('Error','error')}: {color(BASE_URL,'error')} is not defined or invalid; specify it by executing command 'export BASE_URL=<your cpd host>', for example 'export BASE_URL=https://mycpd.com'")
        sys.exit(1)
    
    if USERNAME is None and APIKEY is None:
        if USER_ACCESS_TOKEN is None:
            click.echo(f"{color('Error','error')}: Authorization information is not defined or invalid. Specify either {color('USER_ACCESS_TOKEN','error')}, or both {color('USERNAME','error')} and {color('APIKEY','error')}; For example, specify USERNAME by executing command 'export USERNAME=<your username>'")
            sys.exit(1)
    elif USERNAME is None and APIKEY is not None:
        click.echo(f"{color('Error','error')}: {color(USERNAME,'error')} is not defined or invalid, but {color(APIKEY,'normal')} is valid; specify both environment variables or neither")
        sys.exit(1)
    elif USERNAME is not None and APIKEY is None:
        click.echo(f"{color('Error','error')}: {color(APIKEY,'error')} is not defined or invalid, but {color(USERNAME,'normal')} is valid; specify both environment variables or neither")
        sys.exit(1)
    else:
        credentials = {'username':USERNAME,
                       'api_key':APIKEY}

        USER_ACCESS_TOKEN = get_access_token(credentials)
    
    return USER_ACCESS_TOKEN

def fill_in_access_token(headers,access_token):
    return {k:v.format(access_token=access_token) for k,v in headers.items()}


def download_reference(cpd_version,service='ws',rstudio=False):
    """
    Fetch available runtime names from doc, given a CPD version.

    service: either ws or wml
    rstudio: whether fetches rstudio info; if true, this means fetching ONLY rstudio info because the dockerfile you will
             need to create for rstudio will anyway be different from those for jupyter notebooks
    """
    if service not in ['ws','wml']:
        click.echo(f"{color('Error','error')}: Service {color(service,'error')} is not recognized. The value should be one of [\"ws\",\"wml\"].")
        sys.exit(1)

    if service == 'wml':
        url_doc = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=images-downloading-base-image'
        click.echo(f'Examining doc resources for CPD 4.0 from {color(url_doc)} (same for the latest & historical versions)...')
        page = requests.get(url_doc)
        dfs = pd.read_html(page.text.replace('<br>','|'))
        df_runtime = dfs[0]
        latest_version = df_runtime['CPD patch version'].iloc[0]

        if cpd_version:
            df_runtime = df_runtime[df_runtime['CPD patch version'] == cpd_version]
        else:
            df_runtime = df_runtime[df_runtime['CPD patch version'] == latest_version]
        
        # keep only the amd version tag
        df_runtime['Image version|base-image-version'] = df_runtime['Image version|base-image-version'].apply(lambda x: [v for v in x.split('|') if 'amd' in v][0])


    elif service == 'ws':
        if cpd_version:
            try:
                minor_version = cpd_version.split('.')[2]
                int(minor_version)
            except:
                click.echo(f"{color('Error','error')}: The format of cpd_version is wrong. Example expected value: 4.0.5")
                sys.exit(1)
            
            url_doc_historical = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=versions-documentation-previous-40x-refreshes'
            click.echo(f'Examining historical doc resources for CPD 4.0 for version {color(cpd_version)} from {color(url_doc_historical)}')
            dfs = pd.read_html(url_doc_historical)
            
            dfs_matched = [df for df in dfs if df['PDF'].str.contains(f'-R{minor_version}-').sum() > 0]
            if len(dfs_matched) == 1:
                df_doc = dfs_matched[0]
            else:
                click.echo(f"{color('Error','error')}: {color(len(dfs_matched),'error')} matched record(s) found for cpd version {cpd_version}\nTry the link above and make sure your specified CPD version is available there.")
                sys.exit(1)
                
            filename_doc = df_doc[df_doc['Section']=='Projects']['PDF'].values.tolist()[0]
            url_doc = f'https://www.ibm.com/docs/en/SSQNUZ_4.0/archives/refresh-{minor_version}/{filename_doc}.pdf'
            click.echo(f'WS config files for CPD 4.0 from official doc {color(url_doc)}:')
            
            try:
                from tabula import read_pdf
            except ImportError:
                subprocess.run('pip install tabula-py',shell=True)
                from tabula import read_pdf
            
            dfs = read_pdf(url_doc,pages='all')
            dfs_matched = [df for df in dfs if df.columns[0] == 'JSON configuration file']
            if len(dfs_matched) == 3:
                if not rstudio:
                    df_runtime = dfs_matched[0]
                else:
                    df_runtime = dfs_matched[1]
            else:
                click.echo(f"{color('Error','error')}: {color(len(dfs_matched),'error')} matched table(s) (!=3) found for cpd version {cpd_version}\nTry the link above and make sure the tables for runtime configuration files are there.")
                sys.exit(1)

        else:
            url_doc = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=image-downloading-runtime-configuration'
            click.echo(f'WS config files for CPD 4.0 from official doc {color(url_doc)}:')
            dfs = pd.read_html(url_doc)
            if not rstudio:
                df_runtime = dfs[0]
            else:
                df_runtime = dfs[1]
        
    return df_runtime

def get_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET):
    """
    Download the runtime config files from the cluster to be used as basis for a custom one.
    
    fns: a list of config file names to pull
    """
    access_token = validate_authorization(BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN)
    headers = fill_in_access_token(HEADERS_GET,access_token)
    
    d_config = {}
    for fn in fns:
        url = f"{BASE_URL}/zen-data/v1/volumes/files/{urllib.parse.quote_plus(f'/_global_/config/.runtime-definitions/ibm/{fn}')}"
        r = requests.get(url, headers=headers, verify=False)
        if r.status_code == 200:
            config = r.json()
            d_config[fn] = config#['image']
        else:
            print(r.text)
    return d_config


def put_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_PUT):
    """
    fns: a list of local config file names to push
    """
    access_token = validate_authorization(BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN)
    headers = fill_in_access_token(HEADERS_PUT,access_token)
    url = f"{BASE_URL}/zen-data/v1/volumes/files/{urllib.parse.quote_plus(f'/_global_/config/.runtime-definitions/ibm')}"
    
    for fn in fns:
        res = requests.put(url, headers=headers, files={'upFile': (fn, open(fn, 'rb'))}, verify=False)
        print(fn)
        print(res.text)

if __name__ == '__main__':
    cli()