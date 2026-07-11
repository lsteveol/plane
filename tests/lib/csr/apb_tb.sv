`timescale 1ns/1ps

module tb;
  logic clk;
  logic prstn;
  logic [7:0]  paddr;
  logic        psel;
  logic        penable;
  logic        pwrite;
  logic [31:0] pwdata;
  logic [31:0] prdata;
  logic        pready;

  always #5 clk = ~clk;

  apb_csr_dut dut (
    .apb_pclk(clk),
    .apb_prstn(prstn),
    .apb_paddr(paddr),
    .apb_psel(psel),
    .apb_penable(penable),
    .apb_pwrite(pwrite),
    .apb_pwdata(pwdata),
    .apb_prdata(prdata),
    .apb_pready(pready)
  );

  task apb_write(input [7:0] addr, input [31:0] wdata);
    begin
      @(negedge clk);
      psel    = 1;
      penable = 0;
      pwrite  = 1;
      paddr   = addr;
      pwdata  = wdata;
      @(negedge clk);
      penable = 1;
      @(negedge clk);
      psel    = 0;
      penable = 0;
    end
  endtask

  task apb_read(input [7:0] addr, output [31:0] rdata);
    begin
      @(negedge clk);
      psel    = 1;
      penable = 0;
      pwrite  = 0;
      paddr   = addr;
      @(negedge clk);
      penable = 1;
      @(negedge clk);
      rdata   = prdata;
      psel    = 0;
      penable = 0;
    end
  endtask

  logic [31:0] rdata;

  initial begin
    clk = 0; prstn = 0;
    psel = 0; penable = 0; pwrite = 0;
    paddr = 0; pwdata = 0;

    @(negedge clk); @(negedge clk); @(negedge clk);
    prstn = 1;
    @(negedge clk);

    apb_read(8'h00, rdata);
    if (rdata !== 32'h00000050) begin
      $display("FAIL: reset ctrl = 0x%08x, expected 0x50", rdata);
      $finish;
    end

    apb_read(8'h04, rdata);
    if (rdata !== 32'h00000000) begin
      $display("FAIL: reset data = 0x%08x, expected 0x00", rdata);
      $finish;
    end

    apb_write(8'h00, 32'h00000011);
    apb_read(8'h00, rdata);
    if (rdata !== 32'h00000011) begin
      $display("FAIL: ctrl after write = 0x%08x, expected 0x11", rdata);
      $finish;
    end

    apb_write(8'h04, 32'h0000ABCD);
    apb_read(8'h04, rdata);
    if (rdata !== 32'h0000ABCD) begin
      $display("FAIL: data after write = 0x%08x, expected 0xABCD", rdata);
      $finish;
    end

    $display("PASS");
    $finish;
  end
endmodule
