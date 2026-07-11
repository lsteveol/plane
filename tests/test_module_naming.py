"""Tests for module_prefix and convert_module_names_to_snake_case utils."""
import pytest
from plane import *
from plane import utils


@pytest.fixture(autouse=True)
def reset_utils():
    """Reset utils to defaults before and after each test."""
    original_prefix = utils.module_prefix
    original_snake = utils.convert_module_names_to_snake_case
    yield
    utils.module_prefix = original_prefix
    utils.convert_module_names_to_snake_case = original_snake


class TestSnakeCaseConversion:
    """Tests for to_snake_case helper function."""

    def test_simple_camel_case(self):
        assert utils.to_snake_case("MyApbFanout") == "my_apb_fanout"

    def test_acronym_lead(self):
        assert utils.to_snake_case("IOController") == "io_controller"

    def test_acronym_middle(self):
        assert utils.to_snake_case("MyAPBModule") == "my_apb_module"

    def test_acronym_trailing(self):
        assert utils.to_snake_case("FIFOController") == "fifo_controller"

    def test_digits_mid(self):
        assert utils.to_snake_case("APB3Adapter") == "apb3_adapter"

    def test_digits_trailing(self):
        assert utils.to_snake_case("Counter8") == "counter8"

    def test_all_uppercase(self):
        assert utils.to_snake_case("FIFO") == "fifo"

    def test_already_snake_case(self):
        assert utils.to_snake_case("my_counter") == "my_counter"

    def test_single_word_lowercase(self):
        assert utils.to_snake_case("counter") == "counter"

    def test_single_word_uppercase(self):
        assert utils.to_snake_case("Top") == "top"

    def test_complex_case(self):
        assert utils.to_snake_case("MyTopMod") == "my_top_mod"

    def test_mixed_acronyms(self):
        assert utils.to_snake_case("ABCDef") == "abc_def"


class TestSnakeCaseIntegration:
    """Tests for snake_case conversion in module emission."""

    def test_basic_snake_case(self):
        class MyApbFanout(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                fanout = instance(MyApbFanout())
                fanout.in1 @= self.in1
                self.out1 @= fanout.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = None
        sv = emitVerilog(Top())
        assert "module my_apb_fanout" in sv
        assert "my_apb_fanout myapbfanout" in sv

    def test_blackbox_not_converted(self):
        class TSMCMux(BlackBox):
            def elaborate(self):
                self.a = IO(Input(UInt(1)), name="a")
                self.y = IO(Output(UInt(1)), name="y")

        class Top(Module):
            def elaborate(self):
                self.a = IO(Input(UInt(1)), name="a")
                self.y = IO(Output(UInt(1)), name="y")
                mux = instance(TSMCMux())
                mux.a @= self.a
                self.y @= mux.y

        utils.convert_module_names_to_snake_case = True
        sv = emitVerilog(Top())
        # BlackBox should NOT be converted
        assert "TSMCMux tsmcmux" in sv
        assert "tsmcmux tsmcmux" not in sv


class TestModulePrefix:
    """Tests for module_prefix util."""

    def test_basic_prefix(self):
        class Counter(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                c = instance(Counter())
                c.in1 @= self.in1
                self.out1 @= c.out1

        utils.convert_module_names_to_snake_case = False
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        assert "module my_prefix_Top" in sv
        assert "my_prefix_Counter counter" in sv

    def test_none_prefix(self):
        class Counter(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                c = instance(Counter())
                c.in1 @= self.in1
                self.out1 @= c.out1

        utils.convert_module_names_to_snake_case = False
        utils.module_prefix = None
        sv = emitVerilog(Top())
        assert "module Top" in sv
        assert "module Counter" in sv

    def test_blackbox_not_prefixed(self):
        class TSMCMux(BlackBox):
            def elaborate(self):
                self.a = IO(Input(UInt(1)), name="a")
                self.y = IO(Output(UInt(1)), name="y")

        class Top(Module):
            def elaborate(self):
                self.a = IO(Input(UInt(1)), name="a")
                self.y = IO(Output(UInt(1)), name="y")
                mux = instance(TSMCMux())
                mux.a @= self.a
                self.y @= mux.y

        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        # BlackBox should NOT be prefixed
        assert "TSMCMux tsmcmux" in sv
        assert "my_prefix_TSMCMux" not in sv


class TestOrdering:
    """Tests for snake_case -> dedup -> prefix ordering."""

    def test_snake_plus_prefix(self):
        class MyApbFanout(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                fanout = instance(MyApbFanout())
                fanout.in1 @= self.in1
                self.out1 @= fanout.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        # Order: MyApbFanout -> my_apb_fanout -> my_prefix_my_apb_fanout
        assert "module my_prefix_my_apb_fanout" in sv

    def test_dedup_with_snake(self):
        class Counter(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.in2 = IO(Input(UInt(8)), name="in2")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out2 = IO(Output(UInt(8)), name="out2")
                c1 = instance(Counter())
                c2 = instance(Counter())
                c1.in1 @= self.in1
                c2.in1 @= self.in2
                self.out1 @= c1.out1
                self.out2 @= c2.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = None
        sv = emitVerilog(Top())
        # Two instances of same module should dedup
        assert sv.count("module counter (") == 1

    def test_dedup_with_snake_and_prefix(self):
        class Counter(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.in2 = IO(Input(UInt(8)), name="in2")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out2 = IO(Output(UInt(8)), name="out2")
                c1 = instance(Counter())
                c2 = instance(Counter())
                c1.in1 @= self.in1
                c2.in1 @= self.in2
                self.out1 @= c1.out1
                self.out2 @= c2.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        # Two instances of same module should dedup with prefix
        assert sv.count("module my_prefix_counter (") == 1

    def test_collision_after_snake(self):
        class MyCounter(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class my_counter(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.counter = Reg(UInt(8), init=0, name="counter")
                self.counter @= self.counter + Literal(1, 8)
                self.out1 @= self.counter

        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.in2 = IO(Input(UInt(8)), name="in2")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out2 = IO(Output(UInt(8)), name="out2")
                c1 = instance(MyCounter())
                c2 = instance(my_counter())
                c1.in1 @= self.in1
                c2.clk @= self.clk
                c2.in1 @= self.in2
                self.out1 @= c1.out1
                self.out2 @= c2.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = None
        sv = emitVerilog(Top())
        # MyCounter -> my_counter, my_counter -> my_counter_1 (collision)
        assert sv.count("module my_counter (") == 1
        assert sv.count("module my_counter_1 (") == 1


class TestPackageName:
    """Tests for package name transformation."""

    def test_package_with_snake(self):
        class MyState(PlaneEnum):
            IDLE = 0
            ACTIVE = 1

        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.out = IO(Output(MyState), name="out")
                self.state = Reg(MyState, init=MyState.IDLE, name="state")
                self.state @= MyState.ACTIVE
                self.out @= self.state

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = None
        sv = emitVerilog(Top())
        assert "package top_pkg" in sv
        assert "import top_pkg::*" in sv

    def test_package_with_prefix(self):
        class MyState(PlaneEnum):
            IDLE = 0
            ACTIVE = 1

        class Top(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.out = IO(Output(MyState), name="out")
                self.state = Reg(MyState, init=MyState.IDLE, name="state")
                self.state @= MyState.ACTIVE
                self.out @= self.state

        utils.convert_module_names_to_snake_case = False
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        assert "package my_prefix_Top_pkg" in sv
        assert "import my_prefix_Top_pkg::*" in sv

    def test_package_with_snake_and_prefix(self):
        class MyState(PlaneEnum):
            IDLE = 0
            ACTIVE = 1

        class MyTopMod(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.rst = IO(Input(AsyncLowReset()), name="rst")
                self.out = IO(Output(MyState), name="out")
                self.state = Reg(MyState, init=MyState.IDLE, name="state")
                self.state @= MyState.ACTIVE
                self.out @= self.state

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(MyTopMod())
        # Order: MyTopMod -> my_top_mod -> my_prefix_my_top_mod -> my_prefix_my_top_mod_pkg
        assert "package my_prefix_my_top_mod_pkg" in sv
        assert "import my_prefix_my_top_mod_pkg::*" in sv


class TestSuggestName:
    """Tests for suggest_name with transformations."""

    def test_suggest_name_with_snake(self):
        class Sub(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                sub = instance(Sub().suggest_name("MySub"))
                sub.in1 @= self.in1
                self.out1 @= sub.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = None
        sv = emitVerilog(Top())
        assert "module my_sub" in sv
        assert "my_sub mysub" in sv

    def test_suggest_name_with_prefix(self):
        class Sub(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                sub = instance(Sub().suggest_name("MySub"))
                sub.in1 @= self.in1
                self.out1 @= sub.out1

        utils.convert_module_names_to_snake_case = False
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        assert "module my_prefix_MySub" in sv
        assert "my_prefix_MySub mysub" in sv

    def test_suggest_name_with_snake_and_prefix(self):
        class Sub(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                self.out1 @= self.in1

        class Top(Module):
            def elaborate(self):
                self.in1 = IO(Input(UInt(8)), name="in1")
                self.out1 = IO(Output(UInt(8)), name="out1")
                sub = instance(Sub().suggest_name("MySub"))
                sub.in1 @= self.in1
                self.out1 @= sub.out1

        utils.convert_module_names_to_snake_case = True
        utils.module_prefix = "my_prefix"
        sv = emitVerilog(Top())
        # Order: MySub -> my_sub -> my_prefix_my_sub
        assert "module my_prefix_my_sub" in sv
        assert "my_prefix_my_sub mysub" in sv
