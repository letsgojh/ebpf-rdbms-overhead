/* common/harness/harness_floor.c
 * Group A-1: probe 유무에 따른 syscall 1회당 latency delta 측정.
 * 01_experiment_design.md A-1 "측정 하네스" 스켈레톤(65~93행)을 실행 가능하게 옮긴 것.
 *
 * target_syscall은 Phase 1에서 getpid로 확정(A-1 옵션 2)했다. 반드시 syscall(SYS_getpid)로
 * 직접 호출해야 한다 — glibc의 getpid()는 fork 이후 pid를 캐시해두고 실제 syscall 없이
 * 캐시값을 반환하므로, getpid()를 쓰면 아무것도 측정하지 못한다.
 *
 * TSC → ns 환산. rdtscp는 CPU cycle을 세지, 시간을 세지 않는다. result_schema.json의
 * latency_*_ms 필드에 넣으려면 ns 단위가 필요해서, 시작 시 CLOCK_MONOTONIC 대비 TSC 틱 수를
 * 재는 자체 캘리브레이션으로 cycle→ns 환산 비율을 구한다. 이 환산이 유효하려면 CPU가
 * invariant TSC(constant_tsc && nonstop_tsc, /proc/cpuinfo flags)를 지원해야 한다 —
 * 이 서버(Xeon Gold 6230)는 둘 다 있음을 확인(2026-07-22). 다른 서버에서 돌릴 땐 재확인.
 *
 * 사용법: ./harness_floor <반복횟수 N> <출력파일>
 *   출력 형식은 common/harness/bootstrap_ci.py가 기대하는 "1행 1값" 텍스트(단위: ns).
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <x86intrin.h>

#define WARMUP_ITERS 100000UL
#define DEFAULT_N 10000000UL
#define CALIBRATION_US 100000UL /* 100ms */

static inline uint64_t rdtscp_serialized(void)
{
    unsigned aux;
    uint64_t t;

    _mm_lfence();
    t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

static double calibrate_ns_per_cycle(void)
{
    struct timespec ts_start, ts_end;
    uint64_t tsc_start, tsc_end;
    double elapsed_ns;

    clock_gettime(CLOCK_MONOTONIC, &ts_start);
    tsc_start = rdtscp_serialized();
    usleep(CALIBRATION_US);
    tsc_end = rdtscp_serialized();
    clock_gettime(CLOCK_MONOTONIC, &ts_end);

    elapsed_ns = (double)(ts_end.tv_sec - ts_start.tv_sec) * 1e9
               + (double)(ts_end.tv_nsec - ts_start.tv_nsec);
    return elapsed_ns / (double)(tsc_end - tsc_start);
}

int main(int argc, char **argv)
{
    uint64_t n = argc > 1 ? strtoull(argv[1], NULL, 10) : DEFAULT_N;
    const char *out_path = argc > 2 ? argv[2] : "deltas.txt";
    volatile long ret;
    uint64_t *deltas;
    double ns_per_cycle;
    FILE *f;

    ns_per_cycle = calibrate_ns_per_cycle();
    fprintf(stderr, "calibration: %.6f ns/cycle\n", ns_per_cycle);

    for (uint64_t warm = 0; warm < WARMUP_ITERS; warm++)
        ret = syscall(SYS_getpid);

    deltas = malloc(n * sizeof(uint64_t));
    if (!deltas) {
        perror("malloc");
        return 1;
    }

    for (uint64_t i = 0; i < n; i++) {
        uint64_t start = rdtscp_serialized();
        ret = syscall(SYS_getpid);
        uint64_t end = rdtscp_serialized();
        deltas[i] = end - start;
    }

    f = fopen(out_path, "w");
    if (!f) {
        perror("fopen");
        free(deltas);
        return 1;
    }
    for (uint64_t i = 0; i < n; i++)
        fprintf(f, "%.3f\n", (double)deltas[i] * ns_per_cycle);
    fclose(f);
    free(deltas);

    (void)ret;
    return 0;
}
