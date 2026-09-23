 # Katib Kubernetes Experiments

This directory contains Kubernetes manifests for running hyperparameter tuning experiments with Kubeflow Katib.

Return to the [project overview](../README.md) or continue to the
[Ray/KubeRay guide](../ray/README.md).

Katib creates multiple Kubernetes Jobs, runs trials in parallel, collects the `accuracy` metric from the training container, and selects the best hyperparameters.

## Project Versions

| Component | Version |
| --- | --- |
| Kubernetes cluster | `v1.32.2` |
| `kubectl` client | `v1.32.2` |
| kind node image | `kindest/node:v1.32.2` |
| Katib | `v0.17.0` |
| Python | `3.11` |
| Training image | `katib-training:local` |

Kustomize is bundled with `kubectl`. Its version does not need to match Katib.

## Prerequisites

Install and start Docker Desktop. Install the Kubernetes command-line tools with Homebrew:

```bash
brew install kubectl kind
```

Verify the tools:

```bash
docker --version
kubectl version --client
kind version
```

## Create the kind Cluster

Create the Kubernetes `v1.32.2` cluster:

```bash
kind create cluster \
	--name katib-demo \
	--image kindest/node:v1.32.2
```

Select the context and verify the cluster:

```bash
kubectl config use-context kind-katib-demo
kubectl get nodes
kubectl version
```

The node should show `Ready`, and the client and server versions should be compatible.

## Build and Load the Training Image

Run these commands from the repository root:

```bash
docker build -f katib/Dockerfile -t katib-training:local .
```

Load the local image into the kind node:

```bash
kind load docker-image katib-training:local \
	--name katib-demo
```

Verify that the node can access the image:

```bash
docker exec katib-demo-control-plane \
	crictl images | grep katib-training
```

The Kubernetes manifests use `imagePullPolicy: IfNotPresent`, so Kubernetes uses the image loaded into kind instead of trying to pull it from Docker Hub.

## Install Katib

Install the stable Katib `v0.17.0` control plane:

```bash
kubectl apply -k \
	"github.com/kubeflow/katib.git/manifests/v1beta1/installs/katib-standalone?ref=v0.17.0"
```

Wait for the components to become ready:

```bash
kubectl get pods -n kubeflow -w
```

Press `Ctrl+C` when the pods show `Running` and ready. This stops only the watch command.

Verify the installation:

```bash
kubectl get pods -n kubeflow
kubectl get crd experiments.kubeflow.org
```

## Create the Experiment Namespace

Create the namespace and enable Katib metrics-collector injection:

```bash
kubectl apply -f katib/kubernetes/namespace.yml
```

The label allows Katib to inject its metrics collector into trial pods and read metrics from the training logs.

## Test a Plain Kubernetes Job

Before using Katib, run the training image as a normal Kubernetes Job:

```bash
kubectl apply \
  -f katib/kubernetes/job.yml \
  -n ml-tuning
```

Inspect the Job, pod, and logs:

```bash
kubectl get jobs -n ml-tuning
kubectl get pods -n ml-tuning
kubectl logs -n ml-tuning job/katib-training-test
```

Expected output:

```text
accuracy=0.972222
```

## Run the Katib Experiment

The Experiment manifest is [experiment.yml](kubernetes/experiment.yml). It searches the `C` and `max_iter` values using random search.

Apply it:

```bash
kubectl apply -f katib/kubernetes/experiment.yml
```

Watch trial status:

```bash
kubectl get trials -n ml-tuning -w
```

In another terminal, inspect the Jobs and pods:

```bash
kubectl get jobs -n ml-tuning
kubectl get pods -n ml-tuning
```

Check the Experiment status:

```bash
kubectl get experiment \
	digits-hyperparameter-tuning \
	-n ml-tuning
```

Inspect the selected result and trial observations:

```bash
kubectl describe experiment \
	digits-hyperparameter-tuning \
	-n ml-tuning

kubectl get trials -n ml-tuning -o yaml
```

The Experiment is configured with `parallelTrialCount: 3`, so up to three trial Jobs can run at the same time. It evaluates up to six configurations because `maxTrialCount` is `6`.

## Hyperparameters and Metrics

The Experiment searches these parameters:

| Katib parameter | Python argument | Range |
| --- | --- | --- |
| `c` | `--C` | `0.01` to `10.0` |
| `max-iter` | `--max_iter` | `100` to `500` |

Katib substitutes the values in the trial command:

```yaml
args:
	- "--C=${trialParameters.c}"
	- "--max_iter=${trialParameters.max-iter}"
```

The training script prints:

```text
accuracy=0.972222
```

The metric name must match the objective configuration:

```yaml
objectiveMetricName: accuracy
```

The objective is to maximize accuracy toward `0.98`.

## Viewing Trial Logs

The current Experiment sets:

```yaml
retainAllTrials: true
```

This keeps trial Jobs and pods after completion. List the trial pods:

```bash
kubectl get pods -n ml-tuning
```

Then view a trial's training-container logs:

```bash
kubectl logs -n ml-tuning <trial-pod-name> -c training-container
```

If an Experiment has already completed, use a new name before rerunning it:

```yaml
metadata:
	name: digits-hyperparameter-tuning-v2
```

## Troubleshooting

### Check the active context

```bash
kubectl config current-context
kubectl get nodes
```

The expected context is `kind-katib-demo`.

### Check Katib components

```bash
kubectl get pods -n kubeflow
```

### Inspect Experiment events

```bash
kubectl describe experiment \
	digits-hyperparameter-tuning \
	-n ml-tuning
```

### Inspect a trial

```bash
kubectl describe trial <trial-name> -n ml-tuning
```

### Reload the local image

If a trial cannot find `katib-training:local`, rebuild and reload it:

```bash
docker build -f katib/Dockerfile -t katib-training:local .
kind load docker-image katib-training:local --name katib-demo
```

### Fix namespace metrics injection

```bash
kubectl label namespace ml-tuning \
	katib.kubeflow.org/metrics-collector-injection=enabled \
	--overwrite
```

## Cleanup

Delete the Experiment:

```bash
kubectl delete experiment \
	digits-hyperparameter-tuning \
	-n ml-tuning
```

Delete the namespace and its resources:

```bash
kubectl delete namespace ml-tuning
```

Delete the kind cluster:

```bash
kind delete cluster --name katib-demo
```

## Architecture

```text
Katib Experiment
			 |
			 v
Katib Controller
			 |
			 +--> Trial Job 1 --> training container --> accuracy
			 +--> Trial Job 2 --> training container --> accuracy
			 +--> Trial Job 3 --> training container --> accuracy
			 |
			 v
Best hyperparameters
```

This project demonstrates parallel hyperparameter-search orchestration with Katib. A future KubeRay extension can distribute one training trial across multiple worker pods.
