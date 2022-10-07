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
import numpy as np
import re
import copy

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import pandas as pd # to format tables
pd.set_option('display.max_colwidth', None)

import ssl
ssl._create_default_https_context = ssl._create_unverified_context # fixed ssl certificate issue when downloading html in pandas

USER_ACCESS_TOKEN = os.getenv('USER_ACCESS_TOKEN')
USERNAME = os.getenv('CPD_USERNAME')
APIKEY = os.getenv('CPD_APIKEY')

BASE_URL = os.getenv('CPD_BASE_URL',os.getenv('RUNTIME_ENV_APSX_URL'))

HEADERS_GET = {'authorization':'Bearer {access_token}'}

CPD_VERSION_LATEST = '4.5.2'

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

    if cpd_version is None:
        click.echo(f"{color('cpd_version')} is not specified, using the latest version {color(CPD_VERSION_LATEST)}\n")
        cpd_version = CPD_VERSION_LATEST
    
    flag_df_config = False # whether the downloaded df contains runtime config files that need to be processed further, or the images info is already listed
        
    if service == 'wml':
        cpu = True # wml service
        if gpu or a:
            click.echo(f"{color('Error','error')}: Service {color('wml','error')} supports python cpu environments for online & batch deployments (which yield a REST API), where only CPU inference is allowed. As a result you cannot specify \"--gpu\" or \"--all\". \nIf you intend to run GPU inference through a notebook/script job deployment in WML space, the underlying environments and all the steps are the same as WS environments, as in this case WML space leverages WS runtimes, so please use \"--service ws\" instead.")
            sys.exit(1)
        df_runtime = download_reference(cpd_version,service)

        if cpd_version.startswith('4.0.'):
            df_runtime['image'] = 'cp.icr.io/cp/cpd/' + df_runtime['Image name|base-image-name'] + ':' + df_runtime['Image version|base-image-version']
            print(df_runtime)
        else:
            flag_df_config = True
            df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-py')]
            print(df_runtime)

            click.echo(f"\nFetching config files on CPD {color(BASE_URL)}...")
            fns = df_runtime['JSON configuration file'].tolist()
            
            d_config = get_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
            
            if len(d_config) == 0:
                click.echo(f"\nNo config file. Cannot output base image list.")
                sys.exit(1)
                        
            df = pd.DataFrame({'filename':d_config.keys(),
                            'image':[config['image'] for config in d_config.values()]})
            
            click.echo(f'\nWML config files on CPD {color(BASE_URL)}, selected fields:')
            print(df)

    elif service == 'ws':
        flag_df_config = True
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
        
        
    # export
    if export_fn is not None:
        if flag_df_config:
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
        else:
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


# -------- cli group: custom --------
@cli.group()
def custom():
    """
    custom WS configs
    """
    pass


@custom.command()
@click.option('--runtime-filename-pattern','-r',type=str,default='ws-applications-{filename}',help='config file name pattern, where the original config filename which the custom file is based on indicates in {filename}')
@click.option('--cpd-version','-v',type=str,default=None,help='a specific CPD version; if not specified, information of the latest version is pulled')
def list(runtime_filename_pattern,cpd_version):
    """
    List custom runtime configurations with known name patterns
    """
    df_runtime = download_reference(cpd_version)
    print(df_runtime)
    df_runtime = df_runtime[df_runtime['JSON configuration file'].str.contains('-py')]
    fns = df_runtime['JSON configuration file'].tolist()
    fns_custom = [runtime_filename_pattern.format(filename=fn) for fn in fns]
    
    d_config = get_config_files(fns_custom,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)
    
    if len(d_config) == 0:
        click.echo(f"\nNo custom config file with pattern {color(runtime_filename_pattern)}.")
        sys.exit(1)
                
    df = pd.DataFrame({'filename':d_config.keys(),
                       'image':[config['image'] for config in d_config.values()]})
    
    click.echo(f'\nWS custom config files on CPD {color(BASE_URL)} with pattern {color(runtime_filename_pattern)}, selected fields:')
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
@click.option('--dir-dockerfile',type=str,default='.',help='directory to the location of the dockerfile')
@click.option('--base-image-list',type=str,required=True,help='a filename of a text file containing base image names, one at a line')
@click.option('--custom-image-name-pattern',type=str,default='{image_name}-custom',help='pattern of the custom image name; where the original image name which the custom file is based on is referred to as {image_name}')
@click.option('--docker-build-args',type=str,default='',help='Other docker build args to attach, for example "--no-cache=true"')
@click.option('--push',is_flag=True,help='whether to include push as well')
@click.option('--registry-url',type=str,default='us.icr.io',help='registry url to store the custom image')
@click.option('--registry-namespace',type=str,default='custom-image',help='registry namespace to store the custom image')
@click.option('--docker-push-args',type=str,default='',help='Other docker push args')
def build(dir_dockerfile, base_image_list, custom_image_name_pattern, docker_build_args,
          push, registry_url, registry_namespace, docker_push_args):
    """
    Build (and optionally push) the custom images. 
    Note that you may need to run "docker login cp.icr.io" first, to make sure you have configured access to the
    image registry of CPD, from where to download the base image.

    push: if this flag is added, make sure that you have either supplied values to these arguments or the default values are good: --registry-url, --registry-namespace
    """

    with open(base_image_list) as f:
        l_base_image = [base_image.replace('\n','') for base_image in f.readlines()]

    #os.chdir(dir_dockerfile)
    #print('Changed working directory to',dir_dockerfile)

    for base_image in l_base_image:
        if '@' in base_image:
            image_name = base_image.split('@')[0].split('/')[-1] # ws uses @
        elif ':' in base_image:
            image_name = base_image.split(':')[0].split('/')[-1] # wml uses :
        else:
            image_name = base_image
        image_name_custom = custom_image_name_pattern.format(image_name=image_name)
        print(f'Building custom image {image_name_custom} based on {image_name}')
        
        print(f'pwd')
        res = subprocess.run('pwd',shell=True)

        cmd = f'docker build {dir_dockerfile} --build-arg base_image_tag={base_image} -t {image_name_custom} {docker_build_args}'
        print(f'Executing command: {cmd}')
        res = subprocess.run(cmd,shell=True)
        if res.returncode != 0:
            click.echo(f"{color('FAILED','error')}: return code {res.returncode}. {res}")
        else:
            print(f'Finished building custom image {image_name_custom}')

            if push:
                cmd = f'docker tag {image_name_custom} {registry_url}/{registry_namespace}/{image_name_custom}'
                print(f'Executing command: {cmd}')
                subprocess.run(cmd,shell=True)

                cmd = f'docker push {registry_url}/{registry_namespace}/{image_name_custom} {docker_push_args}'
                print(f'Executing command: {cmd}')
                subprocess.run(cmd,shell=True)
                print(f'Finished pushing custom image as {registry_url}/{registry_namespace}/{image_name_custom}')


@custom.command()
@click.option('--base-image-list',type=str,help='a filename of a text file containing base image names, one at a line')
@click.option('--custom-image-name-pattern',type=str,default='{image_name}-custom',help='pattern of the custom image name; where the original image name which the custom file is based on is referred to as {image_name}')
@click.option('--image-name',type=str,help='the image name to push, an alternative to providing a base image list & name pattern')
@click.option('--registry-url',type=str,default='us.icr.io',help='registry url to store the custom image')
@click.option('--registry-namespace',type=str,default='custom-image',help='registry namespace to store the custom image')
@click.option('--docker-push-args',type=str,default='',help='Other docker push args')
def push(base_image_list, custom_image_name_pattern, image_name,
         registry_url, registry_namespace, docker_push_args):
    """
    Push the custom images. 
    Note that you may need to run "docker login <your-container-registry>" first, to make sure you have configured access to the
    image registry for custom images.

    You need to provide either an image name to push (easy for the case to push one single image), or provide 
    both the base image list and the custom image name pattern from where multiple images can be pushed in batch.
    """

    if image_name is None:
        if base_image_list is None and custom_image_name_pattern is None:
            click.echo(f"{'Error','error'}: you need to provide either --image-name, or both --base-image-list and --custom-image-name-pattern")
            sys.exit(1)

    if image_name is not None:
        image_name_custom = image_name
        print(f'Pushing custom image {image_name_custom}')
        
        cmd = f'docker tag {image_name_custom} {registry_url}/{registry_namespace}/{image_name_custom}'
        print(f'Executing command: {cmd}')
        subprocess.run(cmd,shell=True)

        cmd = f'docker push {registry_url}/{registry_namespace}/{image_name_custom} {docker_push_args}'
        print(f'Executing command: {cmd}')
        res = subprocess.run(cmd,shell=True)

        if res.returncode != 0:
            click.echo(f"{color('FAILED','error')}: return code {res.returncode}. {res}")
        else:
            print(f'Finished pushing custom image as {registry_url}/{registry_namespace}/{image_name_custom}')   
    else:
        with open(base_image_list) as f:
            l_base_image = [base_image.replace('\n','') for base_image in f.readlines()]

        for base_image in l_base_image:
            if '@' in base_image:
                image_name = base_image.split('@')[0].split('/')[-1] # ws uses @
            elif ':' in base_image:
                image_name = base_image.split(':')[0].split('/')[-1] # wml uses :
            else:
                image_name = base_image
            image_name_custom = custom_image_name_pattern.format(image_name=image_name)
            
            cmd = f'docker tag {image_name_custom} {registry_url}/{registry_namespace}/{image_name_custom}'
            print(f'Executing command: {cmd}')
            subprocess.run(cmd,shell=True)
            
            print(f'Pushing custom image {image_name_custom} based on {image_name}')
            
            cmd = f'docker push {registry_url}/{registry_namespace}/{image_name_custom} {docker_push_args}'
            print(f'Executing command: {cmd}')
            res = subprocess.run(cmd,shell=True)

            if res.returncode != 0:
                click.echo(f"{color('FAILED','error')}: return code {res.returncode}. {res}")
            else:
                print(f'Finished pushing custom image as {registry_url}/{registry_namespace}/{image_name_custom}')   



@custom.command()
@click.option('--gpu',is_flag=True,help='whether to create WS gpu runtime config')
@click.option('--jupyter',is_flag=True,help='whether to create WS jupyter notebook runtime config')
@click.option('--jupyterlab',is_flag=True,help='whether to create WS jupyterlab runtime config')
@click.option('--jupyter-all',is_flag=True,help='whether to create WS jupyterlab AND jupyterlab runtime configs, equivalent to --jupyter --jupyterlab')
@click.option('--rstudio',is_flag=True,help='whether to create custom rstudio env; this overwrites these flags: --gpu, --jupyter, --jupyterlab, --jupyter-all')
@click.option('--python-version','-py',type=str,default=None,help='a specific python version as basis; if not specified, custom config will be generated for all available WS python versions')
@click.option('--service',type=str,default='ws',help='the service to list the base mage for; currently supports either ws or wml')
@click.option('--storage-volume',type=str,default='cc-home-pvc',help='the storage volume display name for WML software specification, which mounts an existing pvc called cc-home-pvc')
@click.option('--framework',type=str,default=None,help='framework in WML images; default to the one used for regular cpu inference; if specified, the value should be one of autoai-kb, autoai-ts, pytorch-onnx, cuda, do, tensorflow')
@click.option('--base-software-spec','-s',type=str,default=None,help='base software spec to be used, for example runtime22.1-py3.9; if not specified, it will try to automatically determine one')
@click.option('--software-spec-pattern','-ss',type=str,default=None,help='software spec name pattern, where the original software spec filename is referred to as {filename} and image name referred to as {image_name}')
@click.option('--runtime-filename-pattern','-r',type=str,default='custom-{filename}',help='runtime config file name pattern, where the original config filename which the custom file is based on is referred to as {filename}; default value: custom-{filename}')
@click.option('--display-name-pattern','-d',type=str,default='{display_name} (custom)',help='display name pattern, where the original display name which the custom file is based on is referred to as {display_name}; default value: {display_name} (custom)')
@click.option('--image-name-pattern','-i',type=str,default='us.icr.io/custom-image/{image_name}-custom:2',help='image name pattern, where the original image name which the custom file is based on is referred to as {image_name}; default value: us.icr.io/custom-image/{image_name}-custom:2')
@click.option('--cpd-version','-v',type=str,default=None,help='a specific CPD version used to pull the default config list from doc; if not specified, information of the latest version is pulled')
@click.option('--dry-run',is_flag=True,help='performing all the steps except for the last step to register the new custom config in WS')
def register(gpu,jupyter,jupyterlab,jupyter_all,rstudio,python_version,
             service,
             storage_volume, framework, base_software_spec, software_spec_pattern,
            runtime_filename_pattern,display_name_pattern,image_name_pattern,cpd_version,dry_run):
    """
    List custom runtime configurations with known name patterns.
    For WS environments, you may specify flags such as gpu, jupyter, jupyterlab, jupyter_all, or rstudio.
    For WML environments, the above flags do not apply, as it only supports python cpu runtimes with no jupyter or jupyterlab.
    """
    if service not in ['ws','wml']:
        click.echo(f"{color('Error','error')}: The value for argument {color('service','error')} should be one of ['ws', 'wml'].")
        sys.exit(1)

    frameworks = ['autoai-kb', 'autoai-ts', 'pytorch-onnx', 'cuda', 'do', 'tensorflow']
    if framework is not None and framework not in frameworks:
        click.echo(f"{color('Error','error')}: The value for argument {color('framework','error')} should be one of {frameworks}.")
        sys.exit(1)
    
    if not cpd_version.startswith('4.5.') and not cpd_version.startswith('4.0.'):
        click.echo(f"{color('Error','error')}: {color('cpd-version','error')} should be either on 4.5 or 4.0 (e.g., 4.5.2).")
        sys.exit(1)

    if service == 'wml':
        if gpu or jupyter or jupyterlab or jupyter_all or rstudio:
            click.echo(f"{color('Error','error')}: Service {color('wml','error')} supports python cpu environments for online & batch deployments (which yield a REST API), where only CPU inference is allowed. As a result you cannot specify flags such as \"--gpu\" or \"--rstudio\". \nIf you intend to run GPU inference through a notebook/script job deployment in WML space, the underlying environments and all the steps are the same as WS environments, as in this case WML space leverages WS runtimes, so please use \"--service ws\" instead.")
            sys.exit(1)
        
        from cpd_sdk_plus import storage_volume_utils as sv
        if cpd_version.startswith('4.5.'):
            if '::' not in storage_volume:
                click.echo(f"{color('Error','error')}: storage volume name {color(storage_volume,'error')} does not have the namespace specified (example name expected: cpd-instance::cc-home-pvc-sv); check your storage volume name")
                sys.exit(1)

        # 1. check if storage volume exists
        click.echo(f"Checking whether storage volume {color(storage_volume)} exists on cluster {color(BASE_URL)}...")
        d_storage_volume = sv.list_storage_volumes()
        if storage_volume in d_storage_volume.keys():
            click.echo(f"Found! {d_storage_volume[storage_volume]}")
        else:
            click.echo(f"{color('Error','error')}: Cannot find storage volume {color(storage_volume,'error')}. Please manually create a storage volume in CPD that points to an existing PVC cc-home-pvc, then provide the storage volume name to the command accordingly. Support for auto-creation will be implemented soon.")
            sys.exit(1)
        
        # 2. determine runtime config filename to be used as the base
        df_runtime = download_reference(cpd_version,service)
        if cpd_version.startswith('4.5.'):
            df_runtime = df_runtime[df_runtime['Image description'].str.contains('Python')]
            df_runtime['py_v'] = df_runtime['JSON configuration file'].apply(lambda x: [e[2:] for e in x.split('-') if e.startswith('py')][0])
            df_runtime = df_runtime.rename(columns={'JSON configuration file':'filename'})
        else:
            df_runtime['image'] = 'cp.icr.io/cp/cpd/' + df_runtime['Image name|base-image-name'] + ':' + df_runtime['Image version|base-image-version']
            df_runtime['py_v'] = df_runtime['Image name|base-image-name'].apply(lambda x: [e[2:] for e in x.split('-') if e.startswith('py')][0])
            df_runtime['filename'] = df_runtime['py_v'].apply(lambda x: f'wml-deployment-runtime-py{x}-server.json')
            #print(df_runtime)

        fns_runtime = df_runtime['filename'].values.tolist()

        # 3. get all existing software specification files
        dir_sv_software_spec = '_global_/config/environments/software-specifications'
        l_files = sv.list_files(path=dir_sv_software_spec,volume_display_name=storage_volume)
        l_filenames = [x['path'] for x in l_files]

        # 4. get all needed runtime config files
        d_config = get_config_files(fns_runtime,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET)

        # 5. loop through all custom images (proxy: runtimes)
        d_config_new = {}
        for fn_runtime, py_v in zip(df_runtime['filename'],df_runtime['py_v']):
            image_name = d_config[fn_runtime]['image'].split('@')[0].split('/')[-1]
            image_name_new = image_name_pattern.format(image_name=image_name)

            # 5.1 find the matching software spec
            if base_software_spec is not None:
                fn_software_spec = base_software_spec + '.json'
            else:
                if py_v in ['36','37','38']:
                    fns_software_spec = [x for x in l_filenames if x.startswith(f'python{py_v}')]
                elif py_v in ['39']:
                    py_v_with_dot = py_v[0] + '.' + py_v[1:]
                    fns_software_spec = [x for x in l_filenames if py_v_with_dot in x]
                else:
                    click.echo(f"{color('Error','error')}: python version {py_v} is not supported by this CLI.")
                    sys.exit(1)
                
                # filter the resulting software specs
                flag_regular = False if isinstance(framework,str) else True
                fns_software_spec_filtered = copy.deepcopy(fns_software_spec) if flag_regular else []
                for x in fns_software_spec:  
                    if not flag_regular and framework in x:
                            fns_software_spec_filtered.append(x)
                    else:
                        if x.endswith('-edt.json') or 'spark' in x: # edt is for wmla, spark env is not tested in this tool
                            fns_software_spec_filtered.remove(x)

                        for y in frameworks:
                            if y in x:
                                try:
                                    fns_software_spec_filtered.remove(x)
                                except:
                                    pass # it might have already been removed from the filtered list
                                break
                click.echo(f"{color(len(fns_software_spec_filtered))} matched software specs: {color(fns_software_spec_filtered)}")

                if len(fns_software_spec_filtered) != 1:
                    click.echo(f"{color('Error','error')}: The number of matched software spec is not 1. This is not expected.")
                    sys.exit(1)
            
                fn_software_spec = fns_software_spec_filtered[0]

            # 5.2 fetch the matching software spec
            os.makedirs('./tmp',exist_ok=True)
            fn_software_spec_new = software_spec_pattern.format(filename=fn_software_spec,      image_name=image_name)
            sv.download(dir_sv_software_spec+'/'+fn_software_spec,volume_display_name=storage_volume,
                        path_target=f'./tmp/{fn_software_spec_new}')
            
            # 5.3 create a new software spec based on the matching one
            software_spec = json.load(open(f'./tmp/{fn_software_spec_new}'))

            # https://www.ibm.com/docs/en/cloud-paks/cp-data/4.5.x?topic=images-creating-new-base-software-specification
            software_spec['metadata']['name'] = fn_software_spec_new[:-5] # remove the .json part
            software_spec['entity']['software_specification']['built_in'] = False

            display_name = software_spec['entity']['software_specification']['display_name']
            display_name_new = display_name_pattern.format(display_name=display_name)
            software_spec['entity']['software_specification']['display_name'] = display_name_new
            
            with open(f'./tmp/{fn_software_spec_new}','w') as f:
                print("Writing new software spec to file ./tmp/" + fn_software_spec_new)
                json.dump(software_spec, f)
            
            # 5.4 upload the new software spec to the storage volume
            sv.upload(f'./tmp/{fn_software_spec_new}',volume_display_name=storage_volume,
                      path_target=dir_sv_software_spec+'/'+fn_software_spec_new)

            # 5.5 create a new runtime config based on the matching one
            
            config = {
                    "displayName": display_name_pattern.format(display_name=d_config[fn_runtime]['displayName']),
                    "description": "WML custom image",
                    "author": "",
                    "tested": True,
                    "isService": True,
                    "features": ["wml"],
                    "runtimeType": "wml",
                    "software_specification_name": fn_software_spec_new[:-5], # remove .json
                    "image": image_name_new
                }
            
            fn_new = runtime_filename_pattern.format(filename=fn_runtime)
            d_config_new[fn_new] = config

    # service == "ws"
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
                fn_new = runtime_filename_pattern.format(filename=fn)

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


# -------- cli group: pkg --------
@cli.group()
def pkg():
    """
    check available packages
    """
    pass

@pkg.command()
@click.option('--pkg-type',type=str,default='microdnf',help='the type of packages defined by the installation command; only supports microdnf')
@click.option('--channel','-c',type=str,multiple=True,help='a specific channel to list packages from; can specify multiple by using this argument for multipe times, one channel at a time')
@click.option('--channel-only',is_flag=True,help='whether to only list the channels')
@click.option('--x86-only',is_flag=True,help='whether to only include packages compatible with x86_64 (.x86_64.rpm or .noarch.rpm)')
@click.option('--export-fn',type=str,default=None,help='the output filename')
@click.option('--export-format',type=str,default='csv',help='csv exports only the base images to be used later')
@click.option('--overwrite','-o',is_flag=True,help='whether to overwrite the output file if it exists')
def list(pkg_type,channel,channel_only,x86_only,export_fn,export_format,overwrite):
    if pkg_type == 'microdnf':
        l_repo = list_channel(pkg_type)
        if channel_only:
            sys.exit(0)
        else:
            df_pkg = list_pkg(pkg_type,channel,l_repo,x86_only)
        
        # export
        if export_fn is not None:
            if export_format == 'csv':
                if os.path.exists(export_fn):
                    click.echo(f"Export filename {color(export_fn)} already exists.")
                    if not overwrite:
                        click.echo(f"{color('Stopped','error')}")
                        sys.exit(1)
                    else:
                        click.echo(f"Overwriting file {color(export_fn)}...")
                else:
                    click.echo(f"Export filename {color(export_fn)} does not exist.")
                
                df_pkg.to_csv(export_fn,index=False)
                click.echo(f"Package list written to {color(export_fn,'pass')}")
        else:
            print(df_pkg)

@pkg.command()
@click.option('--name',type=str,required=True,help='the package name to search for')
@click.option('--pkg-type',type=str,default='microdnf',help='the type of packages defined by the installation command; only supports microdnf')
@click.option('--channel','-c',type=str,multiple=True,help='a specific channel to list packages from; can specify multiple by using this argument for multipe times, one channel at a time')
@click.option('--x86-only',is_flag=True,help='whether to only include packages compatible with x86_64 (.x86_64.rpm or .noarch.rpm)')
@click.option('--file',type=str,help='path to an already exported file from pkg list or pkg search command, from where to do the search')
@click.option('--export-fn',type=str,default=None,help='the output filename')
@click.option('--export-format',type=str,default='csv',help='csv exports only the base images to be used later')
@click.option('--overwrite','-o',is_flag=True,help='whether to overwrite the output file if it exists')
def search(name,pkg_type,channel,x86_only,file,export_fn,export_format,overwrite):
    if pkg_type == 'microdnf':
        if file:
            df_pkg = pd.read_csv(file)
        else:
            l_repo = list_channel(pkg_type)
            df_pkg = list_pkg(pkg_type,channel,l_repo,x86_only)
        
        df_pkg = df_pkg[df_pkg['pkg'].str.contains(name)].reset_index(drop=True)
        df_pkg = df_pkg.drop(['channel'],axis=1)
        
        # export
        if export_fn is not None:
            if export_format == 'csv':
                if os.path.exists(export_fn):
                    click.echo(f"Export filename {color(export_fn)} already exists.")
                    if not overwrite:
                        click.echo(f"{color('Stopped','error')}")
                        sys.exit(1)
                    else:
                        click.echo(f"Overwriting file {color(export_fn)}...")
                else:
                    click.echo(f"Export filename {color(export_fn)} does not exist.")
                
                df_pkg.to_csv(export_fn,index=False)
                click.echo(f"Package list written to {color(export_fn,'pass')}")
        else:
            print(df_pkg)


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
        click.echo(f"{color('Error','error')}: {color('CPD_BASE_URL','error')} is not defined or invalid; specify it by executing command 'export CPD_BASE_URL=<your cpd host>', for example 'export CPD_BASE_URL=https://mycpd.com'")
        sys.exit(1)
    
    if USERNAME is None and APIKEY is None:
        if USER_ACCESS_TOKEN is None:
            click.echo(f"{color('Error','error')}: Authorization information is not defined or invalid. Specify either {color('USER_ACCESS_TOKEN','error')}, or both {color('CPD_USERNAME','error')} and {color('CPD_APIKEY','error')}; For example, specify CPD_USERNAME by executing command 'export CPD_USERNAME=<your username>'")
            sys.exit(1)
    elif USERNAME is None and APIKEY is not None:
        click.echo(f"{color('Error','error')}: {color('CPD_USERNAME','error')} is not defined or invalid, but {color('CPD_APIKEY','normal')} is valid; specify both environment variables or neither")
        sys.exit(1)
    elif USERNAME is not None and APIKEY is None:
        click.echo(f"{color('Error','error')}: {color('CPD_APIKEY','error')} is not defined or invalid, but {color('CPD_USERNAME','normal')} is valid; specify both environment variables or neither")
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
        if cpd_version.startswith('4.0.'):
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
        elif cpd_version.startswith('4.5.'):
            if cpd_version == CPD_VERSION_LATEST:
                url_doc = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.5.x?topic=pbci-downloading-runtime-configuration'
                click.echo(f'WS config files for CPD 4.5 from official doc {color(url_doc)}:')
                dfs = pd.read_html(url_doc)
                df_runtime = dfs[0]
            else:
                # only 4.5.2 is supported as I haven't found the historical refreshes for 4.5.x
                click.echo(f"{color('Error','error')}: this tool does not support cpd version {cpd_version}\nContact the author if you have a need.")
                sys.exit(1)
        else:
            click.echo(f"{color('Error','error')}: this tool does not support cpd version {cpd_version}\nContact the author if you have a need.")
            sys.exit(1)

    elif service == 'ws':
        if cpd_version.startswith('4.0.'):
            if cpd_version.endswith('.9'):
                url_doc = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=image-downloading-runtime-configuration'
                click.echo(f'WS config files for CPD 4.0 from official doc {color(url_doc)}:')
                dfs = pd.read_html(url_doc)
                if not rstudio:
                    df_runtime = dfs[0]
                else:
                    df_runtime = dfs[1]
            else:
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
        elif cpd_version.startswith('4.5.'):
            if cpd_version == CPD_VERSION_LATEST:
                url_doc = 'https://www.ibm.com/docs/en/cloud-paks/cp-data/4.5.x?topic=image-downloading-runtime-configuration'
                click.echo(f'WS config files for CPD 4.5 from official doc {color(url_doc)}:')
                dfs = pd.read_html(url_doc)
                if not rstudio:
                    df_runtime = dfs[0]
                else:
                    df_runtime = dfs[1]
            else:
                # only 4.5.2 is supported as I haven't found the historical refreshes for 4.5.x
                click.echo(f"{color('Error','error')}: this tool does not support cpd version {cpd_version}\nContact the author if you have a need.")
                sys.exit(1)
        else:
            click.echo(f"{color('Error','error')}: this tool does not support cpd version {cpd_version}\nContact the author if you have a need.")
            sys.exit(1)

    return df_runtime

def get_config_files(fns,BASE_URL,USERNAME,APIKEY,USER_ACCESS_TOKEN,HEADERS_GET,return_raw=False):
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
        if return_raw:
            d_config[fn] = r
        else:
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


def drop_invalid_val(l,vals_to_drop=[],drop_nan=True):
    res = []
    for x in l:
        if x not in vals_to_drop:
            if drop_nan:
                try:
                    if np.isnan(x):
                        pass
                    else:
                        res.append(x)
                except:
                    res.append(x)
            else:
                res.append(x)
    return res


def list_channel(pkg_type):
    if pkg_type == 'microdnf':
        url = 'http://rpmfind.net/linux/centos/8-stream/'
        l_repo = pd.read_html(url)[0]['Name'].values.tolist()
        l_repo = drop_invalid_val(l_repo,['Parent Directory'])
        l_repo = [x[:-1] for x in l_repo]
        click.echo(f"Searchable channels for {color(pkg_type)}:")
        print('\n'.join(l_repo))
        return l_repo
    else:
        click.echo(f"{color('Error','error')}: --pkg-type {pkg_type} only supports microdnf at the moment")
        sys.exit(1)

def list_pkg(pkg_type,channel,l_repo,x86_only):
        if len(channel)>0:
            l_repo_reduced = []
            for c in channel:
                if c not in l_repo:
                    click.echo(f"{color('Warning','error')}: Specified channel {c} is not in searchable channels. However, it might be usable. You could proceed with using it in the dockerfile and see if it works.")
                else:
                    l_repo_reduced.append(c)
            click.echo(f"{color(len(l_repo_reduced))} channels to proceed with: {l_repo_reduced}")
            if len(l_repo_reduced) == 0:
                sys.exit(0)
        else:
            l_repo_reduced = l_repo
            click.echo(f"{color(len(l_repo_reduced))} channels to proceed with: {l_repo_reduced}")
        
        df_pkg = pd.DataFrame()
        if pkg_type == 'microdnf':
            for repo in l_repo_reduced:
                url = f"http://rpmfind.net/linux/centos/8-stream/{repo}/x86_64/os/Packages/"
                click.echo(f"Fetching list of packages from channel {color(repo)} ({color(url)})...")
                try:
                    res = requests.get(url)
                except:
                    click.echo(f"Channel {repo} does not have packages organized in the regular way. It may not be a valid one for rpm packages.")
                    next
                l_pkg = re.findall(r'href="(.+?)"',res.content.decode())
                l_pkg = [x for x in l_pkg if x.endswith('.rpm')]

                if x86_only:
                    l_pkg = [x for x in l_pkg if x.endswith('.x86_64.rpm') or x.endswith('.noarch.rpm')]
                l_link = [f"http://rpmfind.net/linux/centos/8-stream/{repo}/x86_64/os/Packages/{x}" for x in l_pkg]
                df_pkg_cur = pd.DataFrame({'channel':repo,
                                            'pkg':l_pkg,
                                            'link':l_link})
                df_pkg = pd.concat([df_pkg,df_pkg_cur])
            return df_pkg
        else:
            click.echo(f"{color('Error','error')}: --pkg-type {pkg_type} only supports microdnf at the moment")
            sys.exit(1)

if __name__ == '__main__':
    cli()