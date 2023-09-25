import datajoint as dj
import inspect
import json


logger = dj.logger

# Set up connection credentials and store config
source_conn = dj.connection.Connection(
    dj.config["database.host"],
    dj.config["database.user"],
    dj.config["database.password"],
)

target_conn = dj.connection.Connection(
    dj.config["custom"]["target_database.host"],  # type: ignore
    dj.config["custom"]["target_database.user"],  # type: ignore
    dj.config["custom"]["target_database.password"],  # type: ignore
)

# schema names to validate

schema_names = {'arseny_analysis_corr',
                'arseny_analysis_pop',
                'arseny_cf',
                'arseny_cf_copy1',
                'arseny_lab',
                'arseny_learning',
                'arseny_learning_analysis',
                'arseny_learning_imaging',
                'arseny_learning_lick2d',
                'arseny_learning_photostim',
                'arseny_learning_photostim_anal',
                'arseny_learning_photostim_paper',
                'arseny_learning_plots',
                'arseny_learning_ridge',
                'arseny_learning_tracking',
                'arseny_map_analysis',
                'arseny_map_lab_restore',
                'arseny_s1alm',
                'arseny_s1alm_analysis',
                'arseny_s1alm_ephys',
                'arseny_s1alm_ephys_copy1',
                'arseny_s1alm_experiment',
                'arseny_s1alm_experiment2',
                'arseny_s1alm_experiment_copy1',
                'arseny_s1alm_misc',
                'arseny_s1alm_misc_copy1',
                'arseny_watercue_analysis',
                'arseny_workerlog',
                'lee_meso_analysis',
                'map_lab',
                'talch012_Lick2DtalP',
                'talch012_lick2d',
                'tzionan_lick2dtz'}


def main():
    """
    Validation of schemas migration
        1. for the provided list of schema names - validate all schemas have been migrated
        2. for each schema - validate all tables have been migrated
        3. for each table, validate all entries have been migrated
    """
    missing_schemas = []
    missing_tables = {}
    missing_entries = {}

    for schema_name in schema_names:
        logger.info(f"Validate schema: {schema_name}")
        source_vm = dj.create_virtual_module(
            f"source_{schema_name}",
            schema_name,
            connection=source_conn,
        )
        try:
            target_vm = dj.create_virtual_module(
                f"target_{schema_name}",
                schema_name,
                connection=target_conn,
            )
        except dj.errors.DataJointError:
            missing_schemas.append(schema_name)
            continue

        missing_tables[schema_name] = []
        missing_entries[schema_name] = {}

        for attr in dir(source_vm):
            obj = getattr(source_vm, attr)
            if isinstance(obj, dj.user_tables.UserTable) or (
                    inspect.isclass(obj) and issubclass(obj, dj.user_tables.UserTable)
            ):
                source_tbl = obj
                try:
                    target_tbl = getattr(target_vm, attr)
                except AttributeError:
                    missing_tables[schema_name].append(source_tbl.table_name)
                    continue
                logger.info(f"\tValidate entry count: {source_tbl.__name__}")
                source_entry_count = len(source_tbl())
                target_entry_count = len(target_tbl())
                missing_entries[schema_name][source_tbl.__name__] = {
                    'entry_count_diff': source_entry_count - target_entry_count,
                    'db_size_diff': source_tbl().size_on_disk - target_tbl().size_on_disk}

    return {"missing_schemas": missing_schemas,
            "missing_tables": missing_tables,
            "missing_entries": missing_entries}


if __name__ == "__main__":
    validation_result = main()
    with open('./migration_validation.json', 'w') as f:
        json.dump(validation_result, f)
