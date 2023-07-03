# influxdb_client_3/__init__.py

import pyarrow as pa
from pyarrow.flight import FlightClient, Ticket, FlightCallOptions
from influxdb_client import InfluxDBClient as _InfluxDBClient
from influxdb_client import WriteOptions as WriteOptions
from influxdb_client.client.write_api import WriteApi as _WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS, PointSettings
from influxdb_client.domain.write_precision import WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client import Point
import json

from influxdb_client_3.read_file import upload_file


def write_client_options(**kwargs):
    return kwargs


def flight_client_options(**kwargs):
    return kwargs  # You can replace this with a specific data structure if needed


class InfluxDBClient3:
    def __init__(
            self,
            host=None,
            org=None,
            database=None,
            token=None,
            _write_client_options=None,
            _flight_client_options=None,
            **kwargs):
        """
        This class provides an interface for interacting with an InfluxDB server, simplifying common operations such as writing, querying.
        * host (str, optional): The hostname or IP address of the InfluxDB server. Defaults to None.
        * org (str, optional): The InfluxDB organization name to be used for operations. Defaults to None.
        * database (str, optional): The database to be used for InfluxDB operations. Defaults to None.
        * token (str, optional): The authentication token for accessing the InfluxDB server. Defaults to None.
        * write_options (ANY, optional): Exposes InfuxDB WriteAPI options.
        * **kwargs: Additional arguments to be passed to the InfluxDB Client.
        """
        self._org = org
        self._database = database
        self._write_client_options = _write_client_options if _write_client_options is not None else write_client_options(write_options=SYNCHRONOUS)
        self._client = _InfluxDBClient(
            url=f"https://{host}",
            token=token,
            org=self._org,
            **kwargs)
        
        self._write_api = _WriteApi(
            self._client, **self._write_client_options)

        self._flight_client_options = _flight_client_options if _flight_client_options is not None else {}
        self._flight_client = FlightClient(
            f"grpc+tls://{host}:443",
            **self._flight_client_options)
        
        # create an authorization header
        self._options = FlightCallOptions(
            headers=[(b"authorization", f"Bearer {token}".encode('utf-8'))])

    def write(self, record=None, **kwargs):
        """
        Write data to InfluxDB.

        :type database: str
        :param record: The data point(s) to write.
        :type record: Point or list of Point objects
        :param kwargs: Additional arguments to pass to the write API.
        """
        try:
            self._write_api.write(
                bucket=self._database, record=record, **kwargs)
        except Exception as e:
            print(e)

    def write_file(
            self,
            file,
            measurement_name=None,
            tag_columns=[],
            timestamp_column='time',
            **kwargs):
        """
        Write data from a  file to InfluxDB.

        :param file: The file to write.
        :param kwargs: Additional arguments to pass to the write API.
        """
        try:
            rf = upload_file(file)
            Table = rf.load_file()

            if isinstance(Table, pa.Table):
                df = Table.to_pandas()
            else:
                df = Table
            print(df)

            measurement_column = None

            if measurement_name is None:
                if 'measurement' in df.columns:
                        measurement_column = 'measurement'
                elif 'iox::measurement' in df.columns:
                        measurement_column = 'iox::measurement'

                if measurement_column is not None:
                    unique_measurements = df[measurement_column].unique()
                    for measurement in unique_measurements:
                        df_measurement = df[df[measurement_column] == measurement]
                        df_measurement = df_measurement.drop(columns=[measurement_column])
                        print(df_measurement)
                        self._write_api.write(bucket=self._database, record=df_measurement,
                                            data_frame_measurement_name=measurement,
                                            data_frame_tag_columns=tag_columns,
                                            data_frame_timestamp_column=timestamp_column)
                else:
                    print("'measurement' column not found in the dataframe.")
            else:
                if 'measurement' in df.columns:
                    df = df.drop(columns=['measurement'])
                self._write_api.write(bucket=self._database, record=df,
                                    data_frame_measurement_name=measurement_name,
                                    data_frame_tag_columns=tag_columns,
                                    data_frame_timestamp_column=timestamp_column)
        except Exception as e:
            print(e)

    def query(self, query, language="sql", mode="all"):
        # create a flight client pointing to the InfluxDB
        # create a ticket
        ticket_data = {
            "database": self._database,
            "sql_query": query,
            "query_type": language}

        ticket_bytes = json.dumps(ticket_data)
        ticket = Ticket(ticket_bytes)

        # execute the query and return all the data
        flight_reader = self._flight_client.do_get(ticket, self._options)

        if mode == "all":
            # use read_all() to get all of the data as an Arrow table
            return flight_reader.read_all()
        # use read_all() to get all of the data as an Arrow table
        elif mode == "pandas":
            return flight_reader.read_pandas()
        elif mode == "chunk":
            return flight_reader
        elif mode == "reader":
            return flight_reader.to_reader()
        elif mode == "schema":
            return flight_reader.schema
        else:
            return flight_reader.read_all()

    def close(self):
        # Clean up resources here.
        # Call close method of _write_api and _flight_client, if they exist.
        if hasattr(self._write_api, 'close'):
            self._write_api.close()
        if hasattr(self._flight_client, 'close'):
            self._flight_client.close()
        if hasattr(self._client, 'close'):
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = [
    "InfluxDBClient3",
    "Point",
    "PointSettings",
    "SYNCHRONOUS",
    "ASYNCHRONOUS",
    "write_client_options",
    "WritePrecision",
    "flight_client_options",
    "WriteOptions"]
