import argparse

from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--C", type=float, default=1.0, help="Inverse of regularization strength")
    parser.add_argument("--max_iter", type=int, default=100, help="Maximum number of iterations for the solver")
    parser.add_argument("--test_size", type=float, default=0.2, help="Proportion of the dataset to include in the test split")

    return parser.parse_args()

def main():
    args = parse_args()

    data = load_digits()

    x_train, x_test, y_train, y_test = train_test_split(data.data, data.target, test_size=args.test_size, random_state=42, stratify=data.target)

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=args.C, max_iter=args.max_iter, random_state=42)
    )

    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"accuracy={accuracy:.6f}")


if __name__ == "__main__":
    main()