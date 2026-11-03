from dataclasses import dataclass
from enum import Enum

from ui.next_run import _block_type_value


class ExampleBlockType(str, Enum):
    WORK = "work"
    RECOVERY = "recovery"


@dataclass
class Block:
    block_type: object


def test_block_type_helper_accepts_enum():
    assert _block_type_value(Block(ExampleBlockType.WORK)) == "work"


def test_block_type_helper_accepts_plain_string():
    assert _block_type_value(Block("work")) == "work"


def test_block_type_helper_normalises_case_and_space():
    assert _block_type_value(Block("  RECOVERY ")) == "recovery"


def test_block_type_helper_handles_missing_value():
    class Empty:
        pass
    assert _block_type_value(Empty()) == ""
