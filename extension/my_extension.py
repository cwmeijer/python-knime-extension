import logging
import knime_extension as knext
from csvw import CSVW
import pandas as pd
from urllib import request
import json

LOGGER = logging.getLogger(__name__)

my_category = knext.category(
    path="/",
    level_id="eye_of_beholder",
    name="Eye of Beholder",
    description="This is the KNIME extension that includes nodes for the Eye of Beholder project.",
    icon="icon.png",
)


def validate_metadata_url(url):
    assert url, "Metadata URL is empty!"

    with request.urlopen(url) as url:
        try:
            data = json.load(url)
        except json.JSONDecodeError as ex:
            # code here works for the purpose of indicating the issue
            # but may cause confusion to not showing the exact exception
            raise Exception("Metadata URL is invalid!") from None
        assert "@context" in data.keys(), "Metadata URL is invalid!"

    return True


class CustomError(Exception):
    """
    Custom exception that will show the message from input
    """

    def __init__(self, message):
        super().__init__(message)


@knext.node(
    name="CSVW Validator",
    node_type=knext.NodeType.MANIPULATOR,
    icon_path="icon.png",
    category=my_category,
)
@knext.output_table(
    name="CSV URLs",
    description="A list of Urls to the CSV files referred by the metadata file.",
)
class CSVWValidator:
    """
    This node uses the Python CSVW library (https://github.com/cldf/csvw) for csv files validation. This node assumes that the CSV files are embedded with the metadata file in a remote place. To validate, fill in the URL to the metadata file in the configuration dialog. By executing the node, if the validation passes, it will output a table that contains the list of the validated CSV files. Otherwise, this node will encounter an error.
    """

    metadata_url = knext.StringParameter(
        label="Metadata File URL",
        description="URL to the metadata file",
    )

    def configure(self, configure_context):
        pass

    def execute(self, execute_context):
        validate_metadata_url(self.metadata_url)

        result = CSVW(url=self.metadata_url, validate=True)
        assert result.is_valid, "Validation Failed!"

        csv_list = []
        for i in range(len(result.tables)):
            base = result.tables[i].base
            csv_list.append(result.tables[i].url.resolve(base))
        return knext.Table.from_pandas(pd.DataFrame(csv_list, columns=["csv_urls"]))


@knext.node(
    name="CSVW Reader",
    node_type=knext.NodeType.MANIPULATOR,
    icon_path="icon.png",
    category=my_category,
)
@knext.input_table(
    name="CSV URL", description="The URL to the CSV file that will be normalized."
)
@knext.output_table(name="Normalized Table", description="The normalized table.")
class CSVWReader:
    """
    This node reads the CSV file from an URL and modify the data based on the metadata file by following the CSVW standard.
    """

    metadata_url = knext.StringParameter(
        label="Metadata File URL",
        description="URL to the metadata file",
    )

    def configure(self, configure_context, input_schema):
        assert (
            "csv_urls" in input_schema.column_names
        ), 'Input doesn\'t contains column "csv_urls"!'
        return True

    def execute(self, execute_context, input_table):
        input_df = input_table.to_pandas()
        assert input_df.shape[0] == 1, "None or more than 2 CSVs in the input!"
        csv_url = input_df["csv_urls"].iloc[0]

        validate_metadata_url(self.metadata_url)
        result = CSVW(url=self.metadata_url, validate=True)
        assert result.is_valid, "Validation failed!"

        for t in result.tables:
            base = t.base
            target_url = t.url.resolve(base)
            if target_url == csv_url:
                return knext.Table.from_pandas(pd.DataFrame(t))

        assert False, "Input invalid or not found in Metadata!"
