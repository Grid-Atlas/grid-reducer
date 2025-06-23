from pathlib import Path

import click

from grid_reducer.reducer import OpenDSSModelReducer


@click.command()
@click.option(
    "-f",
    "--opendss-file",
    type=str,
    help="Path to master opendss file for which data is to be extracted.",
)
@click.option(
    "-rs",
    "--remove-secondary",
    type=click.BOOL,
    default=True,
    help="Boolean flag indicating whether to reduce secondary or not.",
)
@click.option(
    "-ap",
    "--aggregate-primary",
    type=click.BOOL,
    default=True,
    help="Boolean flag indicating whether to aggregate primary ckt or not.",
)
@click.option(
    "-tc",
    "--transform-coordinate",
    type=click.BOOL,
    default=True,
    help="Boolean flag indicating whether to transform coordinates or not.",
)
@click.option(
    "-eo",
    "--export-original",
    type=click.BOOL,
    default=True,
    help="Boolean flag indicating whether to export original circuit or not.",
)
@click.option(
    "-ro",
    "--reduced-ckt-output-file",
    type=str,
    default="reduced_ckt.dss",
    help="Path to output dss file for reduced circuit.",
)
@click.option(
    "-oo",
    "--original-ckt-output-file",
    type=str,
    default="original_ckt.dss",
    help="Path to output dss file for original circuit.",
)
def reduce(
    opendss_file: str,
    remove_secondary: bool,
    aggregate_primary: bool,
    transform_coordinate: bool,
    export_original: bool,
    reduced_ckt_output_file: str,
    original_ckt_output_file: str,
):
    reducer_obj = OpenDSSModelReducer(
        Path(opendss_file),
    )
    reduced_ckt = reducer_obj.reduce(
        reduce_secondary=remove_secondary,
        aggregate_primary=aggregate_primary,
        transform_coordinate=transform_coordinate,
    )
    reducer_obj.export(reduced_ckt, reduced_ckt_output_file)
    if export_original:
        reducer_obj.export_original_ckt(original_ckt_output_file)
