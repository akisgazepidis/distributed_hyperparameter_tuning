# Distributed Hyperparameter Tuning on Kubernetes

This project trains the same scikit-learn model through two Kubernetes-based approaches:

1. **Kubeflow Katib** runs multiple independent trials with different hyperparameters and selects the best result.
2. **Ray on Kubernetes with KubeRay** runs one RayJob across a Ray head pod and two worker pods.

The goal is to compare parallel experiment orchestration with distributed task execution on Kubernetes.

## Project Flow

```text
Digits dataset + logistic regression
                |
                v
       Containerized training code
          /                  \
         v                    v
      Katib                 KubeRay
  independent trials     head + 2 workers
         |                    |
         v                    v
    best trial             RayJob metrics
```

Both paths use the digits dataset and report `accuracy`. The target `0.98` is an optimization goal for Katib, not a guaranteed score.

## Runtime Architecture

Docker Desktop runs the kind control-plane container, and Kubernetes runs the Katib and Ray workloads inside that node.

```text
Docker Desktop
└── kind control-plane Docker container
    └── Kubernetes
        ├── Katib controller pods
        │   ├── katib-controller
        │   ├── katib-db-manager
        │   ├── katib-mysql
        │   └── katib-ui
        │
        ├── Katib trial pods
        │   ├── training container
        │   └── metrics collector
        │
        ├── KubeRay operator pod
        │
        └── Ray workload pods
            ├── Ray head container
            ├── Ray worker container
            ├── Ray worker container
            └── RayJob submitter container
```

## Katib and Ray Compared

| | Katib | Ray/KubeRay |
| --- | --- | --- |
| Main purpose | Hyperparameter optimization | Distributed Python/ML execution |
| Unit of work | Independent Kubernetes trial Jobs | One RayJob using Ray workers |
| Coordination | Katib controller | Ray runtime and KubeRay operator |
| Example | Six configurations searched in parallel | Two workers run remote training tasks |
| Result | Best hyperparameters across trials | Aggregated worker metrics |

Katib answers: **which configuration performs best?**

Ray answers: **how can one workload use multiple workers?**

## Training Code

[katib/train.py](katib/train.py) loads the built-in scikit-learn digits dataset, splits it into training and test data, standardizes the features, trains logistic regression, and prints an accuracy metric.

The tunable arguments are:

```text
--C          regularization strength
--max_iter   maximum solver iterations
--test_size  test split proportion
```

The Ray version in [ray/train.py](ray/train.py) uses the same model and hyperparameters, but submits remote training tasks through Ray and reports worker node IDs and the best worker accuracy.

## Repository Guides

- [Katib guide](katib/README.md): create the kind cluster, install Katib, run a plain Kubernetes Job, run the Katib Experiment, inspect trials, and collect the best result.
- [Ray/KubeRay guide](ray/README.md): install Helm and KubeRay, build and load the Ray image, create one head and two workers, submit a RayJob, and retrieve final metrics.

## Current Results

The recorded local runs produced:

```text
Katib best accuracy: 0.963889
Ray best worker accuracy: 0.972222
```

These are example run results, not a promise that every environment will produce identical scores.

## Technology

| Component | Version or value |
| --- | --- |
| Kubernetes | `v1.32.2` |
| kind | `kindest/node:v1.32.2` |
| Katib | `v0.17.0` |
| KubeRay operator | `v1.4.2` |
| Ray | `2.52.0` |
| Python | `3.11` |
| Cluster | kind on Docker Desktop |

## Repository Structure

```text
.
├── README.md
├── katib/
│   ├── Dockerfile
│   ├── train.py
│   ├── README.md
│   └── kubernetes/
├── ray/
│   ├── Dockerfile
│   ├── train.py
│   ├── README.md
│   └── kubernetes/
├── results/
└── requirements.txt
```

Start with the [Katib guide](katib/README.md), then follow the [Ray/KubeRay guide](ray/README.md) to compare both approaches.
