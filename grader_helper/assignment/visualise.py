#!/usr/bin/env python

import pandas as pd


def main():
    print("lets visualise")

    def visualise(
            df: pd.DataFrame,
            bins: int = 80,
            col: str = 'Score') -> None:

        df[col].hist(bins=bins)


if __name__ == '__main__':
    main()
