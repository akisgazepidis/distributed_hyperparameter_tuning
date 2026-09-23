import argparse

import ray
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--C",
        type=float,
        default=1.0,
        help="Inverse of regularization strength",
    )
    parser.add_argument(
        "--max_iter",
        type=int,
        default=100,
        help="Maximum number of solver iterations",
    )
    parser.add_argument(
        "--test_size",
        type=float,
        default=0.2,
        help="Proportion of data used for testing",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of Ray workers",
    )

    return parser.parse_args()


@ray.remote
def train_worker(C, max_iter, test_size, worker_id):
    data = load_digits()

    x_train, x_test, y_train, y_test = train_test_split(
        data.data,
        data.target,
        test_size=test_size,
        random_state=42 + worker_id,
        stratify=data.target,
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=C,
            max_iter=max_iter,
            random_state=42,
        ),
    )

    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)

    node_id = ray.get_runtime_context().get_node_id()

    return {
        "worker_id": worker_id,
        "node_id": node_id,
        "accuracy": accuracy,
    }


def main():
    args = parse_args()

    ray.init(address="auto")

    worker_tasks = [
        train_worker.remote(
            args.C,
            args.max_iter,
            args.test_size,
            worker_id,
        )
        for worker_id in range(args.workers)
    ]

    results = ray.get(worker_tasks)
    best_result = max(results, key=lambda result: result["accuracy"])

    for result in results:
        print(
            f"worker={result['worker_id']} "
            f"node={result['node_id']} "
            f"accuracy={result['accuracy']:.6f}"
        )

    print(
        f"accuracy={best_result['accuracy']:.6f} "
        f"C={args.C} "
        f"max_iter={args.max_iter}"
    )


if __name__ == "__main__":
    main()