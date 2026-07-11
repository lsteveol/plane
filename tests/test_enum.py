from tests.conftest import compile_verilog

import pytest
from plane import *
from plane import utils


class TestEnumFSM:
    def test_fsm_switch_case_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1
            DONE = 2

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.start = IO(Input(Bool()), name="start")
                self.done = IO(Output(Bool()), name="done")
                self.state = Reg(MyState, name="state")
                self.next_state = Wire(MyState, name="next_state")
                self.state @= self.next_state

                with AlwaysComb():
                    self.done @= 0
                    with Switch(self.state):
                        with Case(MyState.IDLE):
                            with When(self.start):
                                self.next_state @= MyState.RUNNING
                        with Case(MyState.RUNNING):
                            self.done @= 1
                            self.next_state @= MyState.DONE
                        with Case(MyState.DONE):
                            self.done @= 1
                            self.next_state @= MyState.IDLE
                        with Default():
                            self.next_state @= MyState.IDLE

        expected = """package M_pkg;
  typedef enum logic [1:0] { IDLE, RUNNING, DONE } MyState_t;
endpackage

module M (
  input  logic clk,
  input  logic start,
  output logic done
);

  import M_pkg::*;

  MyState_t next_state;
  MyState_t state;

  always_comb begin
    done = 1'd0;
    case (state)
      MyState_t::IDLE: begin
        if (start) begin
          next_state = MyState_t::RUNNING;
        end
      end
      MyState_t::RUNNING: begin
        done = 1'd1;
        next_state = MyState_t::DONE;
      end
      MyState_t::DONE: begin
        done = 1'd1;
        next_state = MyState_t::IDLE;
      end
      default: begin
        next_state = MyState_t::IDLE;
      end
    endcase
  end

  always_ff @(posedge clk) begin
    state <= next_state;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_fsm_switch_case_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1
                DONE = 2

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.start = IO(Input(Bool()), name="start")
                    self.done = IO(Output(Bool()), name="done")
                    self.state = Reg(MyState, name="state")
                    self.next_state = Wire(MyState, name="next_state")
                    self.state @= self.next_state

                    with AlwaysComb():
                        self.done @= 0
                        with Switch(self.state):
                            with Case(MyState.IDLE):
                                with When(self.start):
                                    self.next_state @= MyState.RUNNING
                            with Case(MyState.RUNNING):
                                self.done @= 1
                                self.next_state @= MyState.DONE
                            with Case(MyState.DONE):
                                self.done @= 1
                                self.next_state @= MyState.IDLE
                            with Default():
                                self.next_state @= MyState.IDLE

            expected = """module M (
  input  logic clk,
  input  logic start,
  output logic done
);

  localparam MyState_IDLE = 2'd0, MyState_RUNNING = 2'd1, MyState_DONE = 2'd2;

  logic [1:0] next_state;
  logic [1:0] state;

  always_comb begin
    done = 1'd0;
    case (state)
      MyState_IDLE: begin
        if (start) begin
          next_state = MyState_RUNNING;
        end
      end
      MyState_RUNNING: begin
        done = 1'd1;
        next_state = MyState_DONE;
      end
      MyState_DONE: begin
        done = 1'd1;
        next_state = MyState_IDLE;
      end
      default: begin
        next_state = MyState_IDLE;
      end
    endcase
  end

  always_ff @(posedge clk) begin
    state <= next_state;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode

    def test_fsm_when_chain_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.go = IO(Input(Bool()), name="go")
                self.state = Reg(MyState, name="state")
                self.next_state = Wire(MyState, name="next_state")
                self.state @= self.next_state

                with AlwaysComb():
                    self.next_state @= MyState.IDLE
                    with When(self.state == MyState.IDLE):
                        with When(self.go):
                            self.next_state @= MyState.RUNNING

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  input  logic clk,
  input  logic go
);

  import M_pkg::*;

  MyState_t next_state;
  MyState_t state;

  always_comb begin
    next_state = MyState_t::IDLE;
    if (state == MyState_t::IDLE) begin
      if (go) begin
        next_state = MyState_t::RUNNING;
      end
    end
  end

  always_ff @(posedge clk) begin
    state <= next_state;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_fsm_when_chain_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.go = IO(Input(Bool()), name="go")
                    self.state = Reg(MyState, name="state")
                    self.next_state = Wire(MyState, name="next_state")
                    self.state @= self.next_state

                    with AlwaysComb():
                        self.next_state @= MyState.IDLE
                        with When(self.state == MyState.IDLE):
                            with When(self.go):
                                self.next_state @= MyState.RUNNING

            expected = """module M (
  input  logic clk,
  input  logic go
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  logic next_state;
  logic state;

  always_comb begin
    next_state = MyState_IDLE;
    if (state == MyState_IDLE) begin
      if (go) begin
        next_state = MyState_RUNNING;
      end
    end
  end

  always_ff @(posedge clk) begin
    state <= next_state;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode


class TestEnumComparisons:
    def test_eq_comparison_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.state = Reg(MyState, name="state")
                self.state @= MyState.IDLE
                self.out = IO(Output(Bool()), name="out")
                self.out @= self.state == MyState.RUNNING

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  input  logic clk,
  output logic out
);

  import M_pkg::*;

  MyState_t state;

  assign out = (state == MyState_t::RUNNING);

  always_ff @(posedge clk) begin
    state <= MyState_t::IDLE;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_eq_comparison_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.state = Reg(MyState, name="state")
                    self.state @= MyState.IDLE
                    self.out = IO(Output(Bool()), name="out")
                    self.out @= self.state == MyState.RUNNING

            expected = """module M (
  input  logic clk,
  output logic out
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  logic state;

  assign out = (state == MyState_RUNNING);

  always_ff @(posedge clk) begin
    state <= MyState_IDLE;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode

    def test_ne_comparison_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.state = Reg(MyState, name="state")
                self.state @= MyState.IDLE
                self.out = IO(Output(Bool()), name="out")
                self.out @= self.state != MyState.IDLE

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  input  logic clk,
  output logic out
);

  import M_pkg::*;

  MyState_t state;

  assign out = (state != MyState_t::IDLE);

  always_ff @(posedge clk) begin
    state <= MyState_t::IDLE;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_ne_comparison_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.state = Reg(MyState, name="state")
                    self.state @= MyState.IDLE
                    self.out = IO(Output(Bool()), name="out")
                    self.out @= self.state != MyState.IDLE

            expected = """module M (
  input  logic clk,
  output logic out
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  logic state;

  assign out = (state != MyState_IDLE);

  always_ff @(posedge clk) begin
    state <= MyState_IDLE;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode

    def test_lt_comparison_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1
            DONE = 2

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.state = Reg(MyState, name="state")
                self.state @= MyState.IDLE
                self.out = IO(Output(Bool()), name="out")
                self.out @= self.state < MyState.DONE

        expected = """package M_pkg;
  typedef enum logic [1:0] { IDLE, RUNNING, DONE } MyState_t;
endpackage

module M (
  input  logic clk,
  output logic out
);

  import M_pkg::*;

  MyState_t state;

  assign out = (state < MyState_t::DONE);

  always_ff @(posedge clk) begin
    state <= MyState_t::IDLE;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_lt_comparison_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1
                DONE = 2

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.state = Reg(MyState, name="state")
                    self.state @= MyState.IDLE
                    self.out = IO(Output(Bool()), name="out")
                    self.out @= self.state < MyState.DONE

            expected = """module M (
  input  logic clk,
  output logic out
);

  localparam MyState_IDLE = 2'd0, MyState_RUNNING = 2'd1, MyState_DONE = 2'd2;

  logic [1:0] state;

  assign out = (state < MyState_DONE);

  always_ff @(posedge clk) begin
    state <= MyState_IDLE;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode


class TestEnumAssign:
    def test_wire_assign_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.out = IO(Output(MyState), name="out")
                self.out @= MyState.RUNNING

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  output logic out
);

  import M_pkg::*;

  assign out = MyState_t::RUNNING;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_wire_assign_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.out = IO(Output(MyState), name="out")
                    self.out @= MyState.RUNNING

            expected = """module M (
  output logic out
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  assign out = MyState_RUNNING;

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode

    def test_assign_func_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.out = IO(Output(MyState), name="out")
                self.out @= MyState.IDLE

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  output logic out
);

  import M_pkg::*;

  assign out = MyState_t::IDLE;

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_assign_func_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.out = IO(Output(MyState), name="out")
                    self.out @= MyState.IDLE

            expected = """module M (
  output logic out
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  assign out = MyState_IDLE;

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode


class TestEnumMux:
    def test_mux_package(self):
        class MyState(PlaneEnum):
            IDLE = 0
            RUNNING = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.sel = IO(Input(Bool()), name="sel")
                self.state = Reg(MyState, name="state")
                self.state @= Mux(self.sel, MyState.RUNNING, MyState.IDLE)

        expected = """package M_pkg;
  typedef enum logic { IDLE, RUNNING } MyState_t;
endpackage

module M (
  input  logic clk,
  input  logic sel
);

  import M_pkg::*;

  MyState_t state;

  always_ff @(posedge clk) begin
    state <= (sel ? MyState_t::RUNNING : MyState_t::IDLE);
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_mux_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class MyState(PlaneEnum):
                IDLE = 0
                RUNNING = 1

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.sel = IO(Input(Bool()), name="sel")
                    self.state = Reg(MyState, name="state")
                    self.state @= Mux(self.sel, MyState.RUNNING, MyState.IDLE)

            expected = """module M (
  input  logic clk,
  input  logic sel
);

  localparam MyState_IDLE = 1'd0, MyState_RUNNING = 1'd1;

  logic state;

  always_ff @(posedge clk) begin
    state <= (sel ? MyState_RUNNING : MyState_IDLE);
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode


class TestEnumMultiple:
    def test_two_enums_package(self):
        class StateA(PlaneEnum):
            OFF = 0
            ON = 1

        class StateB(PlaneEnum):
            LOW = 0
            MID = 1
            HIGH = 2

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.mode = Reg(StateA, name="mode")
                self.level = Reg(StateB, name="level")
                self.mode @= StateA.OFF
                self.level @= StateB.LOW

        expected = """package M_pkg;
  typedef enum logic { OFF, ON } StateA_t;
  typedef enum logic [1:0] { LOW, MID, HIGH } StateB_t;
endpackage

module M (
  input  logic clk
);

  import M_pkg::*;

  StateA_t mode;
  StateB_t level;

  always_ff @(posedge clk) begin
    mode  <= StateA_t::OFF;
    level <= StateB_t::LOW;
  end

endmodule"""
        sv = emitVerilog(M())
        assert sv == expected

    def test_two_enums_localparam(self):
        old_mode = utils.enum_mode
        utils.enum_mode = "localparam"
        try:
            class StateA(PlaneEnum):
                OFF = 0
                ON = 1

            class StateB(PlaneEnum):
                LOW = 0
                MID = 1
                HIGH = 2

            class M(Module):
                def elaborate(self):
                    self.clk = IO(Input(Clock()), name="clk")
                    self.mode = Reg(StateA, name="mode")
                    self.level = Reg(StateB, name="level")
                    self.mode @= StateA.OFF
                    self.level @= StateB.LOW

            expected = """module M (
  input  logic clk
);

  localparam StateA_OFF = 1'd0, StateA_ON = 1'd1, StateB_LOW = 2'd0, StateB_MID = 2'd1, StateB_HIGH = 2'd2;

  logic mode;
  logic [1:0] level;

  always_ff @(posedge clk) begin
    mode  <= StateA_OFF;
    level <= StateB_LOW;
  end

endmodule"""
            sv = emitVerilog(M())
            assert sv == expected
            compile_verilog(sv)
        finally:
            utils.enum_mode = old_mode


class TestEnumValDunders:
    """Test EnumVal Python-level dunder methods (types.py 165-198)."""

    def setup_method(self):
        class MyOp(PlaneEnum):
            ADD = 0
            SUB = 1
            MUL = 2

        self.ADD = MyOp.ADD
        self.SUB = MyOp.SUB
        self.MUL = MyOp.MUL

    def test_int(self):
        assert int(self.ADD) == 0
        assert int(self.SUB) == 1

    def test_index(self):
        assert self.ADD.__index__() == 0

    def test_hash(self):
        assert hash(self.ADD) == hash(0)
        assert hash(self.SUB) == hash(1)
        assert len({self.ADD, self.SUB}) == 2

    def test_eq_enumval(self):
        from plane.types import EnumVal

        assert self.ADD == EnumVal(type(self.ADD), 0, "ADD", 2)

    def test_eq_int(self):
        assert self.ADD == 0
        assert self.SUB == 1

    def test_eq_other(self):
        assert self.ADD == self.ADD
        assert not (self.ADD == "other")

    def test_ne_enumval(self):
        assert self.ADD != self.SUB

    def test_ne_int(self):
        assert self.ADD != 1
        assert not (self.ADD != 0)

    def test_ne_other(self):
        assert self.ADD != "other"

    def test_lt(self):
        assert self.ADD < self.SUB
        assert self.ADD < 2

    def test_le(self):
        assert self.ADD <= self.ADD
        assert self.ADD <= self.SUB

    def test_gt(self):
        assert self.SUB > self.ADD
        assert self.SUB > 0

    def test_ge(self):
        assert self.SUB >= self.SUB
        assert self.SUB >= self.ADD

    def test_repr(self):
        assert repr(self.ADD) == "MyOp.ADD"


class TestEnumPackageFileWrite:
    """Test emitVerilog with filename and enums (emit.py 118-121)."""

    def test_package_file_written(self, tmp_path):
        class MyState(PlaneEnum):
            IDLE = 0
            RUN = 1

        class M(Module):
            def elaborate(self):
                self.clk = IO(Input(Clock()), name="clk")
                self.r = Reg(MyState, name="state")
                self.r @= MyState.IDLE

        path = tmp_path / "M.sv"
        emitVerilog(M(), filename=str(path))
        pkg_path = tmp_path / "M_pkg.sv"
        assert pkg_path.exists()
        pkg_content = pkg_path.read_text()
        assert "typedef enum logic" in pkg_content
        assert "IDLE" in pkg_content
        assert "RUN" in pkg_content
