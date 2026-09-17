from pathlib import Path
from savescope.core.schema import SchemaManager
from savescope.core.codegen import ParserGenerator

def test_generate_and_run_parser():
    schemas_dir = Path(__file__).parent.parent / "schemas"
    mgr = SchemaManager(schemas_dir)
    schema = mgr.get_schema("Chronicles of Aeloria")
    assert schema is not None

    code = ParserGenerator.generate_code(schema)
    assert "class ChroniclesOfAeloria:" in code
    assert "read_save" in code
    assert "write_save" in code

    # Execute generated code in clean namespace
    namespace = {}
    exec(code, namespace)
    ParserCls = namespace["ChroniclesOfAeloria"]

    save_path = Path(__file__).parent.parent / "samples" / "retro_rpg" / "save_slot1_level1.dat"
    save_obj = ParserCls.read_save(save_path)

    assert save_obj.gold == 500
    assert save_obj.level == 1
    assert save_obj.hp == 100
    assert save_obj.max_hp == 120
    assert save_obj.hero_name == "Aeloria"

    # Modify and write back
    save_obj.gold = 9999
    temp_out = save_path.parent / "test_temp_out.dat"
    try:
        save_obj.write_save(temp_out)
        re_read = ParserCls.read_save(temp_out)
        assert re_read.gold == 9999
        assert re_read.hero_name == "Aeloria"
    finally:
        if temp_out.exists():
            temp_out.unlink()
