import logging
import re
import argparse
import pandas as pd
from torch.utils.data import DataLoader
import torch

from demand_dataset import PointGridDataset
from demand_net import DemandNet


def rmse_loss(y_pred, y):
    return torch.sqrt(torch.mean((y_pred - y) ** 2))


if __name__ == "__main__":
    # Example:
    # python cnn_demand_model/train_model.py --dataset data/train_sample.feather 
    #   --value-range="((-74.0238037109375, -73.91867828369139), (40.6966552734375, 40.81862258911133))"

    parser = argparse.ArgumentParser(description="Model training parameters")
    parser.add_argument("--dataset", help="feather file with points")
    parser.add_argument(
        "--value-range", help="Bounding box - (min_lon, max_lon, min_lat, max_lat)"
    )
    args = parser.parse_args()

    #### Params
    grid_size = (25, 25)
    batch_size = 5
    epochs = 2
    learning_rate = 0.01
    agg_by = "10min"

    # combination of "use_threads=False" and specified columns works faster than
    # all other methods
    data = pd.read_feather(
        args.dataset,
        columns=["pickup_lon", "pickup_lat", "pickup_datetime"],
        use_threads=False,
    )
    print(f'Dataset shape {data.shape}')

    data["time"] = data.pickup_datetime.dt.round(agg_by)
    data["x"] = data.pickup_lon
    data["y"] = data.pickup_lat

    # parse value range from command line
    min_lon, max_lon, min_lat, max_lat = re.findall("[-]?\d+.\d+", args.value_range)
    value_range = ((float(min_lon), float(max_lon)), (float(min_lat), float(max_lat)))
    print(f'Bounding box: {value_range}')

    dataset = PointGridDataset(data, value_range, grid_size, n_steps=1)
    data_loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    print(f"Training dataset size: {len(dataset)}")

    model = DemandNet(grid_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    criterion = rmse_loss

    for epoch in range(epochs):
        print(f"\n{epoch+1} pass through the full training set")

        train_loss = []
        for i, data in enumerate(data_loader):
            inputs, labels = data

            outputs = model(inputs)

            labels = labels.view(labels.size(0), -1)
            loss = criterion(outputs, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss.append(loss.item())
