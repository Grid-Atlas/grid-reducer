from collections import defaultdict
import copy
from typing import Any
import re
from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.altdss.altdss_models import (
    BusConnection,
    Bus,
    Line_SpacingWires,
    Line_LineGeometry,
    Line_LineCode,
    Transformer_XfmrCode,
    LineGeometry_LineSpacing,
)


def get_unique_name(prefix: str, buses: list[str], existing: dict) -> str:
    base_name = f"{prefix}_{'_'.join(buses)}"
    if base_name not in existing.values():
        return base_name
    index = sum(base_name in name for name in existing.values())
    return f"{base_name}_{index}"


def format_bus(bus: BusConnection, bus_mapping: dict) -> BusConnection:
    parts = bus.root.split(".")
    # FunFact: In reduced circuit some of the open switched are just floating
    # with no coordinates. We may want to look at that some time.
    if parts[0] not in bus_mapping:
        return bus
    name = bus_mapping[parts[0]]
    return BusConnection(root=name + ("." + ".".join(parts[1:]) if len(parts) > 1 else ""))


def rename_point_assets(
    field, field_data, bus_mapping, transformer_mappings, line_mappings, asset_mapping
):
    def rename_and_track(item, attr, prefix=None, mapping=None):
        value = getattr(item, attr)
        if prefix and mapping:
            if prefix.lower() not in value.lower():
                raise NotImplementedError(f"{attr} {value} not supported yet for renaming.")
            mapped = prefix + mapping[value.split(".")[1]]
        elif mapping:
            mapped = mapping[value]
        else:
            mapped = value
        setattr(item, attr, mapped)
        new_name = get_unique_name(field.lower(), [mapped.split(".")[-1]], asset_mapping[field])
        asset_mapping[field][item.Name] = new_name
        item.Name = new_name
        updated_items.append(item)

    updated_items = []

    for item in field_data.root.root:
        if hasattr(item, "root") and hasattr(item.root, "Bus1"):
            if getattr(item.root, "Like", None):
                raise NotImplementedError(f"Like {item.root.Like} not supported yet for renaming.")
            item.root.Bus1 = format_bus(item.root.Bus1, bus_mapping)
            bus_names = [item.root.Bus1.root.split(".")[0]]
            if getattr(item.root, "Bus2", None):
                item.root.Bus2 = format_bus(item.root.Bus2, bus_mapping)
                bus_names.append(item.root.Bus2.root.split(".")[0])
            if item.root.Name != "source":
                new_name = get_unique_name(field.lower(), bus_names, asset_mapping[field])
                asset_mapping[field][item.root.Name] = new_name
                item.root.Name = new_name
                updated_items.append(item)

        elif hasattr(item, "SwitchedObj") and item.SwitchedObj:
            rename_and_track(item, "SwitchedObj", prefix="line.", mapping=line_mappings)

        elif hasattr(item, "Transformer") and item.Transformer:
            rename_and_track(item, "Transformer", mapping=transformer_mappings)

        elif hasattr(item, "Element") and item.Element:
            rename_and_track(item, "Element", prefix="line.", mapping=line_mappings)

        elif hasattr(item, "MonitoredObj") and item.MonitoredObj:
            rename_and_track(item, "MonitoredObj", prefix="line.", mapping=line_mappings)

    return updated_items


def get_updated_container(field: str, container: Any, mapping: dict) -> Any:
    new_items = []
    if not hasattr(container, "root") and not hasattr(container.root, "root"):
        raise ValueError(f"Container {container} is not a valid Container.")
    for idx, item in enumerate(container.root.root):
        new_name = get_unique_name(field.lower(), [str(idx)], mapping[field])
        if hasattr(item, "root"):
            mapping[field][item.root.Name] = new_name
            item.root.Name = new_name
        else:
            mapping[field][item.Name] = new_name
            item.Name = new_name
        new_items.append(item)
    new_root = type(container.root).model_construct(root=new_items)
    new_container = type(container).model_construct(root=new_root)
    return new_container


def _rename_buses(buses, bus_mapping):
    return [
        Bus(Name=new_name, **{k: v for k, v in vars(bus).items() if k != "Name" and v is not None})
        for bus, new_name in zip(buses, bus_mapping.values(), strict=False)
    ]


def _update_independent_components(circuit: Circuit, new_circuit: Circuit) -> dict:
    ic_mappings = defaultdict(dict)
    unsupported = {
        "LineCode",
        "LoadShape",
        "TShape",
        "PriceShape",
        "XYcurve",
        "GrowthShape",
        "TCC_Curve",
        "WireData",
        "CNData",
        "TSData",
        "LineGeometry",
        "LineSpacing",
        "XfmrCode",
    }
    for field in Circuit.model_fields:
        if field in unsupported and getattr(circuit, field):
            updated = get_updated_container(field, getattr(circuit, field), ic_mappings)
            setattr(new_circuit, field, updated)
    return ic_mappings


def _rename_lines(new_circuit, bus_mapping, ic_mappings):
    mappings, renamed = {}, []
    for line in new_circuit.Line.root.root:
        root = line.root
        root.Bus1 = format_bus(root.Bus1, bus_mapping)
        root.Bus2 = format_bus(root.Bus2, bus_mapping)
        prefix = "switch" if root.Switch else "line"
        new_name = get_unique_name(prefix, [], mappings)
        mappings[root.Name] = new_name
        root.Name = new_name

        if isinstance(root, Line_LineCode):
            root.LineCode = ic_mappings["LineCode"][root.LineCode]
        elif isinstance(root, Line_LineGeometry):
            root.Geometry = ic_mappings["LineGeometry"][root.Geometry]
        elif isinstance(root, Line_SpacingWires):
            root.Spacing = ic_mappings["LineSpacing"][root.Spacing]

        renamed.append(line)

    new_circuit.Line.root.root = renamed
    return mappings


def _update_line_geometry_fields(new_circuit: Circuit, ic_mappings):
    if not new_circuit.LineGeometry:
        return
    renamed = []
    cond_data_mappings = {**ic_mappings["WireData"], **ic_mappings["CNData"]}
    for geometry in new_circuit.LineGeometry.root.root:
        root = geometry.root
        conductors = [
            f"{c.split('.')[0]}.{cond_data_mappings[c.split('.')[1]]}" if isinstance(c, str) else c
            for c in root.Conductors
        ]
        root.Conductors = conductors
        if isinstance(root, LineGeometry_LineSpacing):
            root.Spacing = ic_mappings["LineSpacing"][root.Spacing]
        renamed.append(geometry)
    new_circuit.LineGeometry.root.root = renamed


def _update_capacitor_control_fields(new_circuit: Circuit, ic_mappings):
    if not new_circuit.CapControl:
        return
    renamed = []
    for capacitor in new_circuit.CapControl.root.root:
        capacitor.Capacitor = ic_mappings["Capacitor"][capacitor.Capacitor]
        renamed.append(capacitor)
    new_circuit.CapControl.root.root = renamed


def _rename_transformers(new_circuit, bus_mapping, ic_mappings):
    mappings, renamed = {}, []
    for transformer in new_circuit.Transformer.root.root:
        root = transformer.root
        root.Bus = [format_bus(b, bus_mapping) for b in root.Bus]
        new_name = get_unique_name(
            "transformer", [b.root.split(".")[0] for b in root.Bus], mappings
        )
        mappings[root.Name] = new_name
        root.Name = new_name
        if isinstance(root, Transformer_XfmrCode):
            root.XfmrCode = ic_mappings["XfmrCode"][root.XfmrCode]
        renamed.append(transformer)

    new_circuit.Transformer.root.root = renamed
    return mappings


def _rename_other_assets(
    circuit, bus_mapping, transformer_mappings, line_mappings, asset_mapping=None
):
    asset_mapping = asset_mapping or {}
    unsupported = {
        "Sensor",
        "GICLine",
        "GICTransformer",
        "GICsource",
        "IndMach012",
        "ESPVLControl",
        "ExpControl",
        "UPFC",
        "UPFCControl",
        "AutoTrans",
        "Spectrum",
    }

    for field in Circuit.model_fields:
        asset_mapping[field] = {}
        if field in {"Line", "Transformer"} or field in unsupported:
            continue
        field_data = getattr(circuit, field)
        if not getattr(field_data, "root", None) or not getattr(field_data.root, "root", None):
            continue
        updated_items = rename_point_assets(
            field, field_data, bus_mapping, transformer_mappings, line_mappings, asset_mapping
        )
        if updated_items:
            root_model = type(field_data.root).model_construct(root=updated_items)
            updated = type(field_data).model_construct(root=root_model)
            setattr(circuit, field, updated)


def _update_postcommands(new_circuit: Circuit, mappings, prefix):
    if not new_circuit.PostCommands:
        return
    updated = []
    for command in new_circuit.PostCommands:
        pattern = rf"{re.escape(prefix)}\.([^\s\.]+)"
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            old_name = match.group(1)
            new_name = mappings.get(old_name, old_name)
            command = re.sub(
                rf"({re.escape(prefix)}\.{re.escape(old_name)})",
                f"{prefix}.{new_name}",
                command,
                flags=re.IGNORECASE,
            )
        updated.append(command)
    new_circuit.PostCommands = updated


def rename_assets(circuit: Circuit) -> Circuit:
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Name = "reduced_ckt"

    bus_mapping = {bus.Name: f"{i}" for i, bus in enumerate(circuit.Bus)}
    new_circuit.Bus = _rename_buses(circuit.Bus, bus_mapping)

    independent_component_mappings = _update_independent_components(circuit, new_circuit)
    _update_line_geometry_fields(new_circuit, independent_component_mappings)
    line_mappings = _rename_lines(new_circuit, bus_mapping, independent_component_mappings)
    transformer_mappings = {}
    if circuit.Transformer:
        transformer_mappings = _rename_transformers(
            new_circuit, bus_mapping, independent_component_mappings
        )
    _rename_other_assets(
        new_circuit,
        bus_mapping,
        transformer_mappings,
        line_mappings,
        independent_component_mappings,
    )
    _update_capacitor_control_fields(new_circuit, independent_component_mappings)
    _update_postcommands(new_circuit, line_mappings, "line")
    _update_postcommands(new_circuit, independent_component_mappings["Capacitor"], "capacitor")
    return new_circuit
