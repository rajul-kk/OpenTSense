// G81b Verilator harness: runs tb (ibex_tb_g81b.v) to completion and writes one VCD per power window.
// Verilator ignores $dumpoff (G81a), so tracing is controlled here: a window file is opened when tb.cyc reaches its
// start and closed at start + len; between windows nothing is dumped. Each file starts with a full value dump,
// as Icarus's $dumpvars at G72's window start.
// Usage: simv +hex=<file> +max=<cycles> +windows=<file: one start cycle per line> +win_len=<cycles> +vcd_prefix=<p>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

#include "Vtb.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

int main(int argc, char** argv) {
    const std::unique_ptr<VerilatedContext> ctx{new VerilatedContext};
    ctx->commandArgs(argc, argv);
    ctx->traceEverOn(true);
    const std::unique_ptr<Vtb> top{new Vtb{ctx.get(), ""}};
    std::vector<long> starts;
    long len = 1000;
    std::string prefix = "w";
    if (const char* a = ctx->commandArgsPlusMatch("windows="); a && *a) {
        std::string f = std::string(a).substr(9);
        FILE* fp = std::fopen(f.c_str(), "r");
        if (!fp) { std::fprintf(stderr, "HARNESS ERROR cannot read windows file %s\n", f.c_str()); return 2; }
        long s;
        while (std::fscanf(fp, "%ld", &s) == 1) starts.push_back(s);
        std::fclose(fp);
    }
    if (const char* a = ctx->commandArgsPlusMatch("win_len="); a && *a) len = std::atol(a + 9);
    if (const char* a = ctx->commandArgsPlusMatch("vcd_prefix="); a && *a) prefix = std::string(a).substr(12);
    // windows must be ascending and non-overlapping, or a window would open late (at the previous one's end)
    for (size_t i = 1; i < starts.size(); ++i)
        if (starts[i] < starts[i - 1] + len) {
            std::fprintf(stderr, "HARNESS ERROR window %zu starts at %ld, before window %zu ends (%ld)\n", i, starts[i],
                         i - 1, starts[i - 1] + len);
            return 2;
        }
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    size_t next = 0;
    long open_until = -1;
    while (!ctx->gotFinish()) {
        top->eval();
        long cyc = (long)top->cyc_o;
        if (open_until < 0 && next < starts.size() && cyc >= starts[next]) {
            char name[512];
            std::snprintf(name, sizeof name, "%s%03zu.vcd", prefix.c_str(), next);
            tfp->open(name);
            open_until = starts[next] + len;
            std::printf("WINDOW %zu open cycle=%ld file=%s\n", next, cyc, name);
            ++next;
        }
        if (open_until >= 0) {
            tfp->dump(ctx->time());
            if (cyc >= open_until) {
                tfp->close();
                open_until = -1;
            }
        }
        if (!top->eventsPending()) break;
        ctx->time(top->nextTimeSlot());
    }
    // a window still open at the end is truncated; a window never reached was never written: both are errors
    bool truncated = open_until >= 0;
    if (truncated) tfp->close();
    top->final();
    delete tfp;
    std::printf("WINDOWS written=%zu requested=%zu truncated=%d\n", next - (truncated ? 1 : 0), starts.size(), truncated);
    if (truncated || next < starts.size()) {
        std::fprintf(stderr, "HARNESS ERROR %zu of %zu windows complete\n", next - (truncated ? 1 : 0), starts.size());
        return 3;
    }
    return 0;
}
