import click
from grid_reducer.cli.reducer import reduce


@click.group()
def cli():
    pass


cli.add_command(reduce)
