import datajoint as dj


db_prefix = "arseny_"

schema_names = set(s for s in dj.list_schemas() if s.startswith(db_prefix))

vmods = {s: dj.create_virtual_module(s, s) for s in schema_names}

diagram = None
for vm in vmods.values():
    if diagram is None:
        diagram = dj.Diagram(vm.schema)
    else:
        diagram += dj.Diagram(vm.schema)

total_bytes = sum([vm.schema.size_on_disk for vm in vmods.values() if vm.schema.list_tables()])
total_gb = total_bytes * 1e-9

upstream_diagram = diagram - 99
upstream_schema_names = set([s.split('.')[0].strip('`')
                             for s in upstream_diagram.topological_sort()]).difference(
    schema_names)

downstream_diagram = diagram + 99
downstream_schema_names = set([s.split('.')[0].strip('`')
                               for s in downstream_diagram.topological_sort()]).difference(
    schema_names)

for s in upstream_schema_names:
    vmods[s] = dj.create_virtual_module(s, s)
for s in downstream_schema_names:
    vmods[s] = dj.create_virtual_module(s, s)

schema_names.add('map_lab')
schema_names.add('lee_meso_analysis')
schema_names.add('talch012_Lick2DtalP')
schema_names.add('talch012_lick2d')
schema_names.add('tzionan_lick2dtz')
