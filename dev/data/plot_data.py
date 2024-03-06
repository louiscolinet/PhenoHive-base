import pandas as pd
import matplotlib.pyplot as plt

# Define column names
column_names = ["Timestamp", "Type", "StationID", "Value"]


def plot_df(name, ndfs, dfs_dic):
    """
    Plot scatter plot of the dataframes in the dictionary
    :param name: name of the plot
    :param ndfs: number of dataframes
    :param dfs_dic: dictionary of dataframes (key: title, value: dataframe)
    """
    _, axs = plt.subplots(ndfs, 1, figsize=(10, 5 * ndfs))
    if ndfs == 1:
        axs = [axs]
    for i, (title, df) in enumerate(dfs_dic.items()):
        axs[i].scatter(df['Timestamp'], df['Value'], label=title)
        axs[i].set_title(title)
        axs[i].set_xlabel('Timestamp')
        axs[i].set_ylabel('Value')
        axs[i].legend()
    plt.savefig(f"{name}_cleaned.png")
    plt.show()


def filter_abnormal_values(df):
    # Calculate the Z-score
    z = (df['Value'] - df['Value'].mean()) / df['Value'].std()
    # Filter the data
    return df[(z < 3) & (z > -3)]


def read_and_process_data(csv_path):
    print(f"Reading data from {csv_path}")
    title = csv_path.split(".")[0]
    # Read Weight data
    df = pd.read_csv(csv_path, header=None, names=column_names)

    # Convert the timestamp to datetime
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Convert the raw values to grams
    # coef = 29.88047808767712
    # df['Value'] = df['Value'] * coef

    # Plot the weight data with different levels of filtering (until no more outliers are detected)
    dfs_dic = {"Original": df}
    for k in range(1, 100):
        prev_len = len(df)
        df = filter_abnormal_values(df)
        if len(df) == prev_len:
            break
        dfs_dic[f"Filtered {k}"] = df
    plot_df(title, len(dfs_dic), dfs_dic)


if __name__ == "__main__":
    csv_paths = ["Weight.csv", "Growth.csv"]
    for csv_path in csv_paths:
        read_and_process_data(csv_path)
