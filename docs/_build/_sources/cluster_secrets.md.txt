# Retrieve or Register Container Registry Secrets

**OpenShift access** is needed to 
- extract the secrets for the base image registry
- add the secrets for the container registry of the custom images for the cluster to pull the newly added images

## Retrieve Secrets
Since 4.0.x, Cloud Pak for Data stores base images for Watson Studio and Watson Machine Learning runtimes in an entitled IBM Container Registry on IBM Cloud (`cp.icr.io`).

Once you installed the Cloud Pak for Data cluster, you will be able to find the entitilement key from the OpenShift backend, if you do not know it.

### 1. Login to the cluster (using oc CLI):
```
oc login --token=xxx --server=xxx
```

### 2. Get the global pull secret
```
oc extract secret/pull-secret -n openshift-config
```

### 3. Extract the seceret and decode it (it's base64 encoded):

```
auth=$(cat .dockerconfigjson| python3 -c "import sys, json; print(json.load(sys.stdin)['auths']['cp.icr.io/cp/cpd']['auth'])")
auth=$(echo $auth | base64 -d)

username=$(echo $auth | cut -d: -f 1)
password=$(echo $auth | cut -d: -f 2)
```
**If you get error complaining `cp.icr.io/cp/cpd` not found, change the first command to:**
```
auth=$(cat .dockerconfigjson| python3 -c "import sys, json; print(json.load(sys.stdin)['auths']['cp.icr.io']['auth'])")
```

## Register Secrets
In order for the cluster to be able to pull the custom images, it needs to know how to access to the container registry for your custom images.

### 1. Get the global pull secret
```
oc extract secret/pull-secret -n openshift-config
```

### 2. Add your secret to it
You can open and modify the file. An example will look like the following:
```
{
    "auths": {
        "cp.icr.io/cp/cpd": {
            "auth": "..."
        },
        "us.icr.io": {
            "auth": "your-new-auth"
        },
        ...
```
Here `us.icr.io` is the container registry for the custom images. How the secrets need to be decoded might be dependent on the container registry service you use.

#### IBM Cloud Container Registry
If you are using IBM Cloud Container Registry, you may follow the steps below. `us.icr.io` is used as an example.

##### 1.1 Create a service id and create policy for it to access ICR
We need a service API key to access `us.icr.io` safely from CPD: https://cloud.ibm.com/docs/Registry?topic=Registry-registry_access > Follow "Creating a service ID API key manually" to create a service id and give it access to ICR.

For example, to give that service id access to the entire ICR service on the account (ideally we probably want to filter by namespace in ICR...):

```
service_id_name=watson-studio-images
ibmcloud iam service-id-create $service_id_name
ibmcloud iam service-policy-create $service_id_name --roles Reader --service-name container-registry
```

Can then list policies for the service id and check:
```
ibmcloud iam service-policies $service_id_name
```

##### 1.2 Create an api key for the service id

```
ibmcloud iam service-api-key-create my-api-key $service_id_name -d "Used to pull images from CPD" --file service_api_key.txt
```

##### 1.3 Add this api key to the image pull secrets of the cluster

We need to append to the list of `"auths"` in `.dockerconfigjson`, adding as key our custom docker registry location and as value a dict containing the auth info to our docker registry. When using a registry on ICR, it's possible to authenticate via apikey to this cluster by using `iamapikey` username and the value of the api key as password. In `.dockerconfigjson` we simply need to concatenate these two values and base64 encode the string:

```
api_key=$(cat service_api_key.txt | python3 -c "import sys, json; print(json.load(sys.stdin)['apikey'])")
echo -n "iamapikey:$api_key" | base64
```

Take this last output and add it to the `.dockerconfigjson`:
```
{
    "auths": {
        "cp.icr.io/cp/cpd": {
            "auth": "..."
        },
        "us.icr.io": {
            "auth": "your-new-auth"
        },
        ...
```

### 3. Apply the new config:
```
oc set data secret/pull-secret -n openshift-config --from-file=.dockerconfigjson=.dockerconfigjson
```

### 4. Restart worker nodes (if on ROKS) to update image pull secrets

As described [here](https://www.ibm.com/docs/en/cloud-paks/cp-data/4.0?topic=upgrade-configuring-your-cluster-pull-software-images) if running on IBM Cloud you need to restart the worker nodes for the new image pull secret to be propagated to all nodes. The previous link references [this portion of the ROKS docs](https://cloud.ibm.com/docs/openshift?topic=openshift-registry#cluster_global_pull_secret) with more details.