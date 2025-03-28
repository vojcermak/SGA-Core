import argparse
import dataclasses
import logging
import os
import random
from io import StringIO
from tempfile import TemporaryDirectory
from typing import Optional, Union
from typing import Type, Any

import pytest
from relic.core import CLI
from relic.core.cli import CliPluginGroup, CliPlugin

from relic.sga.core import Version, MAGIC_WORD
from relic.sga.core.cli import (
    RelicSgaCli,
    RelicSgaUnpackCli,
    RelicSgaInfoCli,
    RelicSgaTreeCli,
    RelicSgaVersionCli,
    RelicSgaListCli,
    EssenceInfoEncoder,
)
from relic.sga.core.serialization import VersionSerializer
from tests.dummy_essencefs import write_random_essencefs, register_randomfs_opener
from tests.util import TempFileHandle


@pytest.mark.parametrize(
    "cli",
    [
        RelicSgaCli,
        RelicSgaUnpackCli,
        RelicSgaInfoCli,
        RelicSgaTreeCli,
        RelicSgaVersionCli,
        RelicSgaListCli,
    ],
)
@pytest.mark.parametrize("parent", [True, False])
def test_init_cli(cli: Union[Type[CliPlugin], Type[CliPluginGroup]], parent: bool):
    parent_parser: Optional[Any] = None
    if parent:
        parent_parser = argparse.ArgumentParser().add_subparsers()

    cli(parent=parent_parser)


def random_nums(a, b, count=1, seed: Optional[int] = None):
    if seed is not None:
        random.seed = seed
    for _ in range(count):
        yield random.randint(a, b)


SEEDS = [8675309, 20040920, 20250318, 500500]


@pytest.mark.parametrize("seed", SEEDS)
def test_cli_tree(seed: int):
    with StringIO() as logFile:
        logging.basicConfig(
            stream=logFile, level=logging.DEBUG, format="%(message)s", force=True
        )
        logger = logging.getLogger()

        register_randomfs_opener()
        with TempFileHandle(".sga") as h:
            with h.open("wb") as w:
                write_random_essencefs(w, seed)
            CLI.run_with("relic", "sga", "tree", h.path, logger=logger)
        print("\nLOG:")
        print(logFile.getvalue())


@pytest.mark.parametrize("add_plugin", [True, False])
def test_cli_list_plugins(add_plugin: bool):
    from relic.sga.core.essencefs.opener import registry

    if add_plugin:
        register_randomfs_opener()
    else:
        for key in list(registry._backing.keys()):
            del registry._backing[key]

    with StringIO() as logFile:
        logging.basicConfig(
            stream=logFile, level=logging.DEBUG, format="%(message)s", force=True
        )
        logger = logging.getLogger()
        CLI.run_with("relic", "sga", "list", logger=logger)
        print("\nLOG:")
        result = logFile.getvalue()
        print(result)
        if add_plugin:
            assert "No Plugins Found" not in result
        else:
            assert "No Plugins Found" in result


@pytest.mark.parametrize("version", [Version(0), Version(1), Version(2)])
@pytest.mark.parametrize("write_magic", [True, False])
def test_cli_version(version: Version, write_magic: bool):
    with StringIO() as logFile:
        logging.basicConfig(
            stream=logFile, level=logging.DEBUG, format="%(message)s", force=True
        )
        logger = logging.getLogger()

        with TempFileHandle(".sga") as h:
            with h.open("wb") as w:
                if write_magic:
                    MAGIC_WORD.write(w)
                VersionSerializer.write(w, version)

            CLI.run_with("relic", "sga", "version", h.path, logger=logger)
        print("\nLOG:")
        result = logFile.getvalue()
        print(result)

        if not write_magic:
            assert "File is not an SGA" in result
        else:
            assert str(version) in result


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("merge_flag", [None, "-m", "--merge", "-i", "--isolate"])
def test_cli_unpack(seed: int, merge_flag: Optional[str]):
    # Only tests that it runs, does not verify output
    # TODO Verify Output
    register_randomfs_opener()
    with StringIO() as logFile:
        logging.basicConfig(
            stream=logFile, level=logging.DEBUG, format="%(message)s", force=True
        )
        logger = logging.getLogger()
        with TempFileHandle(".sga") as h:
            with h.open("wb") as w:
                write_random_essencefs(w, seed)
            with TemporaryDirectory(suffix="-dir") as d:
                args = ["relic", "sga", "unpack", h.path, d]
                if merge_flag is not None:
                    args.append(merge_flag)

                CLI.run_with(*args, logger=logger)
                print("\nLOG:")
                print(logFile.getvalue())


@pytest.mark.parametrize("seed", SEEDS[:2])
@pytest.mark.parametrize("flag", [None, "-m", "--minify"])
@pytest.mark.parametrize("output_is_dir", [True, False])
def test_cli_tree_info(seed: int, flag: Optional[str], output_is_dir: bool):
    # Only tests that it runs, does not verify output
    # TODO Verify Output
    register_randomfs_opener()
    with StringIO() as logFile:
        logging.basicConfig(
            stream=logFile, level=logging.DEBUG, format="%(message)s", force=True
        )
        logger = logging.getLogger()
        with TempFileHandle(".sga") as hw:
            with hw.open("wb") as w:
                write_random_essencefs(w, seed)
            with (
                TempFileHandle(".json")
                if not output_is_dir
                else TemporaryDirectory("-dir")
            ) as hr:
                hr_path = hr.path if isinstance(hr, TempFileHandle) else hr
                args = ["relic", "sga", "info", hw.path, hr_path]
                if flag is not None:
                    args.append(flag)
                CLI.run_with(*args, logger=logger)
                print("\nLOG:")
                print(logFile.getvalue())


def test_info_encoder_dclass():
    enc = EssenceInfoEncoder()

    @dataclasses.dataclass
    class Foo:
        bar: int = 1

    inst = Foo()
    expected = dataclasses.asdict(inst)
    result = enc.default(inst)
    assert result == expected


def test_info_encoder_type_error():
    enc = EssenceInfoEncoder()

    class Foo:
        bar: int = 1

    inst = Foo()
    try:
        result = enc.default(inst)
        expected = str(inst)
        assert result == expected
    except TypeError:
        pytest.fail("Expected the TypeError to be handled")


def test_info_encoder_nondclass():
    enc = EssenceInfoEncoder()
    inst = 1
    result = enc.default(inst)
    expected = str(inst)
    assert result == expected
