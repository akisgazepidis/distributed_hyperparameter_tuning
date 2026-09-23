# Distributed Ray Training on Kubernetes

This guide runs the Ray training application on Kubernetes with KubeRay.
The deployment creates one Ray head pod and two Ray worker pods. A RayJob then
submits `ray/train.py` to the Ray cluster and reports the worker results and
the final accuracy metric.

Return to the [project overview](../README.md) or review the
[Katib guide](../kubernetes/README.md) for the independent-trial approach.

The Ray phase complements the Katib phase in this repository:

```text
Katib  -> multiple independent Kubernetes trial Jobs
Ray    -> one RayJob using multiple Ray workers for distributed task execution
```

## Expected Topology

```text
Kubernetes namespace: ml-tuning
				|
				+--> Ray head pod
				|
				+--> Ray worker pod 1
				|
				+--> Ray worker pod 2
				|
				+--> RayJob submitter pod
```

The RayCluster manifest requests:

```text
1 head pod
2 worker pods
```

The current kind cluster has one Kubernetes node, so the three Ray pods may
run on the same Kubernetes node. They are still separate Ray processes and
workers.

## Versions

| Component | Version or value |
| --- | --- |
| Kubernetes cluster | `v1.32.2` |
| kubectl client | `v1.32.2` |
| kind cluster | `katib-demo` |
| KubeRay operator | `v1.4.2` |
| Ray | `2.52.0` |
| Python | `3.11` |
| Docker image | `ray-training:local` |
| Namespace | `ml-tuning` |

The Ray version in the Python environment, Docker image, and
`raycluster.yml` should remain aligned.

## Repository Files

```text
ray/
├── Dockerfile
├── README.md
├── train.py
└── kubernetes/
    ├── raycluster.yml
    └── rayjob.yml
```

## Prerequisites

Start Docker Desktop and verify the existing kind cluster:

```bash
kubectl config use-context kind-katib-demo
kubectl get nodes
```

The node should be `Ready`.

Verify that the experiment namespace exists:

```bash
kubectl get namespace ml-tuning
```

Create it if necessary:

```bash
kubectl create namespace ml-tuning
```

## 1. Install Helm

Install Helm on macOS:

```bash
brew install helm
```

Verify the installation:

```bash
helm version
```

Helm is the Kubernetes package manager used to install the KubeRay operator.

## 2. Add the KubeRay Chart Repository

Add the official KubeRay chart repository:

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update
```

The first command registers the repository. The second downloads current chart
metadata so Helm can find available versions.

List available operator chart versions:

```bash
helm search repo kuberay/kuberay-operator --versions
```

This project used KubeRay operator version `1.4.2`. Use the version you select
consistently in your local setup and documentation.

## 3. Install the KubeRay Operator

Install the operator into its own namespace:

```bash
helm install kuberay-operator \
	kuberay/kuberay-operator \
	--version 1.4.2 \
	--namespace kuberay-system \
	--create-namespace
```

The operator watches Ray-specific Kubernetes resources and creates the Ray
head and worker pods.

Verify the Helm release and operator pod:

```bash
helm list -n kuberay-system
kubectl get pods -n kuberay-system
```

Wait for the operator deployment:

```bash
kubectl wait \
	--for=condition=Available \
	deployment/kuberay-operator \
	-n kuberay-system \
	--timeout=120s
```

Verify the Ray Custom Resource Definitions:

```bash
kubectl get crd rayclusters.ray.io rayjobs.ray.io rayservices.ray.io
kubectl api-resources | grep ray
```

## 4. Check the Ray Dependencies and Dockerfile

The current repository uses the shared root `requirements.txt`, which contains
Ray and scikit-learn:

```text
ray[default]==2.52.0
scikit-learn
```

Use this `ray/Dockerfile` from the repository root:

```dockerfile
FROM python:3.11-slim

RUN apt-get update \
		&& apt-get install -y --no-install-recommends wget \
		&& rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ray/train.py .

CMD ["python", "train.py"]
```

`wget` is required by the KubeRay health probes. Without it, pods can show
`Running` but remain `0/1 Ready`.

## 5. Build the Ray Image

Run this from the repository root:

```bash
docker build \
  -f ray/Dockerfile \
  -t ray-training:local .
```

The `-f` option selects the Ray Dockerfile, `-t` names the image, and `.` is
the build context. The build context must be the repository root because the
Dockerfile copies `requirements.txt` and `ray/train.py`.

Check the image and Ray version:

```bash
docker images ray-training
docker run --rm ray-training:local \
	python -c "import ray; print(ray.__version__)"
```

## 6. Load the Image into kind

Docker Desktop and the kind node do not share image storage automatically.
Copy the image into the kind cluster:

```bash
kind load docker-image ray-training:local \
	--name katib-demo
```

Verify that the Kubernetes node can see it:

```bash
docker exec katib-demo-control-plane \
	crictl images | grep ray-training
```

The RayCluster manifest uses:

```yaml
image: ray-training:local
imagePullPolicy: IfNotPresent
```

This makes Kubernetes use the locally loaded image instead of pulling it from
a registry.

Repeat the build and load steps whenever `ray/train.py`, `requirements.txt`,
or `ray/Dockerfile` changes.

## 7. Apply the RayCluster

The RayCluster manifest is [kubernetes/raycluster.yml](kubernetes/raycluster.yml).
It defines one head group and a worker group with exactly two replicas.

Apply it:

```bash
kubectl apply \
	-f ray/kubernetes/raycluster.yml
```

Check the custom resource:

```bash
kubectl get raycluster ray-training-cluster \
	-n ml-tuning
```

Watch the pods start:

```bash
kubectl get pods -n ml-tuning -w
```

Wait for this target state:

```text
ray-training-cluster-head-...                 1/1   Running
ray-training-cluster-workers-worker-...       1/1   Running
ray-training-cluster-workers-worker-...       1/1   Running
```

Press `Ctrl+C` to stop watching. This does not stop the Ray cluster.

If a pod remains unready, inspect it:

```bash
kubectl describe pod <ray-pod-name> -n ml-tuning
kubectl logs <ray-pod-name> -n ml-tuning --all-containers
```

## 8. Apply the RayJob

The RayJob manifest is [kubernetes/rayjob.yml](kubernetes/rayjob.yml).
It submits this command to the existing RayCluster:

```text
python /app/train.py --C 2.5 --max_iter 228 --workers 2
```

Apply it after the head and both workers are ready:

```bash
kubectl apply \
	-f ray/kubernetes/rayjob.yml
```

Check the RayJob:

```bash
kubectl get rayjobs -n ml-tuning
```

Watch its status:

```bash
kubectl get rayjobs -n ml-tuning -w
```

The expected status progression is:

```text
Initializing -> Running -> Succeeded
```

Inspect events and the final resource:

```bash
kubectl describe rayjob distributed-training -n ml-tuning
kubectl get rayjob distributed-training -n ml-tuning -o yaml
```

## 9. Retrieve RayJob Submission Logs

KubeRay creates a Kubernetes Job for RayJob submission. Find it:

```bash
kubectl get jobs -n ml-tuning
```

View the submission and streamed application logs:

```bash
kubectl logs -n ml-tuning job/distributed-training
```

The output includes the Ray job ID, for example:

```text
Job 'distributed-training-xf9n8' submitted successfully
```

The same output should contain the Ray application logs and final status.

## 10. Retrieve Ray Application Logs Directly

Get the Ray head pod:

```bash
HEAD_POD=$(kubectl get pods -n ml-tuning \
	-l ray.io/node-type=head \
	-o jsonpath='{.items[0].metadata.name}')
echo "$HEAD_POD"
```

If the submitter output displayed a Ray job ID, retrieve its logs from the
head pod. Replace the example ID with the actual one:

```bash
kubectl exec -n ml-tuning "$HEAD_POD" -- \
	ray job logs distributed-training-xf9n8 \
	--address http://127.0.0.1:8265
```

Check the Ray job status directly:

```bash
kubectl exec -n ml-tuning "$HEAD_POD" -- \
	ray job status distributed-training-xf9n8 \
	--address http://127.0.0.1:8265
```

If the Ray CLI command is not available in the head container, use the
submission Job logs from the previous section. They are the most portable
source for this example.

## 11. Retrieve Final Metrics

The training script prints one line per Ray worker and then the best result:

```text
worker=0 node=<node-id> accuracy=0.963889
worker=1 node=<node-id> accuracy=0.972222
accuracy=0.972222 C=2.5 max_iter=228
```

Print only the final metric from the submission logs:

```bash
kubectl logs -n ml-tuning job/distributed-training \
	| grep '^accuracy='
```

Print all worker metrics:

```bash
kubectl logs -n ml-tuning job/distributed-training \
	| grep -E '^(worker=|accuracy=)'
```

Save the complete output for the repository results directory:

```bash
mkdir -p results/ray
kubectl logs -n ml-tuning job/distributed-training \
	> results/ray/distributed-training.log
```

The final `accuracy=...` line is the best worker accuracy for this RayJob.

## 12. Inspect Ray Resources and Placement

List the Ray pods and their Kubernetes nodes:

```bash
kubectl get pods -n ml-tuning -o wide
```

List only the Ray worker pods:

```bash
kubectl get pods -n ml-tuning \
	-l ray.io/node-type=worker \
	-o wide
```

The two worker results include different Ray node IDs. This confirms that Ray
scheduled the remote tasks on separate Ray worker processes.

## Rerunning the RayJob

Kubernetes resource names must be unique. To rerun the same RayJob, delete the
old RayJob and its submitter Job first:

```bash
kubectl delete rayjob distributed-training \
	-n ml-tuning \
	--ignore-not-found

kubectl delete job distributed-training \
	-n ml-tuning \
	--ignore-not-found
```

Then apply the RayJob again:

```bash
kubectl apply -f ray/kubernetes/rayjob.yml
```

If you change the training code or image, rebuild and reload the image before
rerunning.

## Cleanup

Delete the RayJob:

```bash
kubectl delete rayjob distributed-training -n ml-tuning
```

Delete the RayCluster:

```bash
kubectl delete raycluster ray-training-cluster -n ml-tuning
```

Remove the KubeRay operator:

```bash
helm uninstall kuberay-operator -n kuberay-system
kubectl delete namespace kuberay-system
```

Do not delete the `ml-tuning` namespace if you still want to inspect the Katib
experiment resources.

## Expected Result

At the end of the workflow, you should be able to show:

```text
1 Ray head pod             Running
2 Ray worker pods          Running
1 RayJob submitter         Completed
Ray application job        Succeeded
Final accuracy metric      printed in the logs
```

This demonstrates distributed Ray task execution on Kubernetes. The next
extension is Ray Train, where workers cooperate on one training run, followed
by Ray Tune for distributed hyperparameter search.
