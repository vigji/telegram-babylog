import csv
import time
from datetime import datetime
from pathlib import Path
from venv import logger

from gdrive_log import GDriveLogger


class CsvLogger:
    HEADERS = ["timestamp", "logging_user", "event", "data"]
    TIMESTAMP_FORMAT = "%H:%M:%S %Y-%m-%d"

    def __init__(self, file_path, remote=True):
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            self.set_headers()

        if remote:
            self.remote_logger = GDriveLogger()
        else:
            self.remote_logger = None

    def set_headers(self):
        with open(self.file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(self.HEADERS)

    def log(self, event_dict: dict, timestamp=None):
        if not timestamp:
            timestamp = datetime.now()
        data = [
            timestamp.strftime(self.TIMESTAMP_FORMAT),
            event_dict["logging_user"],
            event_dict["event"],
            event_dict["data"],
        ]

        with open(self.file_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(data)

    @property
    def reader(self):
        with open(self.file_path, mode="r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield row

    def get_last_occurrences(self):
        last_occurrences = {}
        # iterate over reversed rows to get last occurrences.
        # To decide what is last, using timestamp as order could be non-chonological:
        for row in list(self.reader):
            if row["event"] not in last_occurrences:
                add_row = True
            else:
                try:
                    timedelta = datetime.strptime(
                        row["timestamp"], self.TIMESTAMP_FORMAT
                    ) - datetime.strptime(
                        last_occurrences[row["event"]][0], self.TIMESTAMP_FORMAT
                    )
                    add_row = timedelta.total_seconds() > 0
                except Exception as e:
                    logger.error(f"Error in row when computing logging: {row}: {e}")
                    add_row = False

            if add_row:
                last_occurrences[row["event"]] = (
                    row["timestamp"],
                    row["data"],
                    row["logging_user"],
                )

        return last_occurrences

    def _make_line(self, event, timestamp, data, logging_user, time_elapsed=True):
        time_since_last = datetime.now() - datetime.strptime(
            timestamp, self.TIMESTAMP_FORMAT
        )
        minutes_since_last = time_since_last.total_seconds() // 60
        h, min = divmod(minutes_since_last, 60)
        # make timestamp with only hours and minutes:
        timestamp = datetime.strptime(timestamp, self.TIMESTAMP_FORMAT).strftime(
            "%H:%M"
        )
        if time_elapsed:
            time_string = f"{int(h)}h {int(min)}m ago ({timestamp})"
        else:
            time_string = f"({timestamp})"

        # Format to have occurrences columns aligned:
        # return (
        #     f" - {event}"
        #     + (f" ({data})" if data else "")
        #     + f": {logging_user} {time_string}"
        # )
        data_entry = f"{event}" + (f" ({data}):" if data else ":")
        return f" - {data_entry:<15}" + f" {logging_user:<5} {time_string}"

    def format_last_occurrences(self):
        last_occurrences = self.get_last_occurrences()

        mex = f"```\nLast occurrences:\n\n"
        mex += "\n".join(
            [
                self._make_line(event, timestamp, data, logging_user)
                for event, (timestamp, data, logging_user) in last_occurrences.items()
            ]
        )
        mex += "\n```\n"
        return mex

    def get_daily_counts(self):
        daily_counts = {}
        for row in self.reader:
            # check if day is current one
            if datetime.now().strftime("%Y-%m-%d") not in row["timestamp"]:
                continue
            # esclude comments:
            if row["event"] in [
                "comment",
            ]:
                continue

            if row["event"] not in daily_counts:
                daily_counts[row["event"]] = 0
            daily_counts[row["event"]] += 1

        return daily_counts

    def format_daily_counts(self):
        daily_counts = self.get_daily_counts()
        mex = f"```\nDaily counts:\n\n"
        mex += "\n".join(
            [f" - {(event + ':'):<11} {count}" for event, count in daily_counts.items()]
        )
        mex += "\n```\n"
        return mex

    def format_all_rows(self):
        mex = f"```\nAll entries:\n\n"
        row_list = []
        for row in self.reader:
            try:
                row_list.append(
                    self._make_line(
                        row["event"],
                        row["timestamp"],
                        row["data"],
                        row["logging_user"],
                        time_elapsed=False,
                    )
                )
            except Exception as e:
                logger.error(f"Error in row: {row} - {e}")
        mex += "\n".join(row_list)
        mex += "\n ```\n"
        return mex

    @classmethod
    def create(cls, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        filename = "greg_log.csv"
        # filename = "log_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".csv"

        file_path = folder / filename

        return cls(file_path)

    def backup(self):
        key = "AIzaSyAsK0WsaG-dkWqnKNm53OQpIShLR865WPw"
        "gregbot@greg-log.iam.gserviceaccount.com"
        backup_folder = self.file_path.parent / "backups"
        backup_folder.mkdir(parents=True, exist_ok=True)

        # backup file with new filename that keeps track of backup datetime:
        backup_filename = (
            self.file_path.stem
            + "_backup_"
            + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            + self.file_path.suffix
        )

        backup_file_path = backup_folder / backup_filename

        # copy file to backup path:
        with open(self.file_path, "r") as file:
            with open(backup_file_path, "w") as backup_file:
                backup_file.write(file.read())

        if self.remote_logger:
            self.remote_logger.upload(backup_file_path)


if __name__ == "__main__":
    # test the CsvLogger class in a temporary folder:
    from time import sleep

    CSV_LOG_FOLDER = "temp_csv_logs"

    csv_logger = CsvLogger.create(CSV_LOG_FOLDER)
    csv_logger.log({"logging_user": 123, "event": "waking_up", "data": None})
    csv_logger.log({"logging_user": 123, "event": "pooping", "data": None})
    csv_logger.log({"logging_user": 123, "event": "feeding", "data": "sx"})
    csv_logger.log({"logging_user": 123, "event": "feeding", "data": "dx"})
    csv_logger.log({"logging_user": 123, "event": "peeing", "data": None})
    csv_logger.log({"logging_user": 123, "event": "waking_up", "data": "A\n"})
    sleep(1)
    timestamp = datetime.now()
    timestamp = timestamp.replace(day=timestamp.day - 1)
    csv_logger.log(
        {"logging_user": 123, "event": "waking_up", "data": "wrong"},
        timestamp=timestamp,
    )

    print(csv_logger.format_all_rows())
    print(csv_logger.format_last_occurrences())
    print(csv_logger.format_daily_counts())
