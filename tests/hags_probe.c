#include <windows.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

typedef struct { UINT handle; LUID luid; ULONG sources; BOOL precise; } Adapter;
typedef struct { ULONG count; Adapter *adapters; } EnumAdapters;
typedef struct { UINT handle, type; void *data; UINT size; } Query;
typedef LONG (WINAPI *EnumFn)(EnumAdapters *);
typedef LONG (WINAPI *QueryFn)(Query *);
typedef LONG (WINAPI *CloseFn)(UINT *);
__declspec(dllimport) LONG WINAPI D3DKMTQueryAdapterInfo(Query *);
_Static_assert(sizeof(Query) == 24 && offsetof(Query, size) == 16, "query ABI");
_Static_assert(sizeof(Adapter) == 20 && sizeof(EnumAdapters) == 16, "adapter ABI");

static int check(QueryFn query, UINT handle, int patched, const char *binding) {
    UINT caps[2] = {0xdeadbeef, 0x12345678};
    Query q = {handle, 70, caps, 4};
    LONG status = query(&q);
    printf("HAGS binding=%s status=%08lx caps=%08x\n", binding, (unsigned long)status, caps[0]);
    if ((UINT)status != (patched ? 0 : 0xc0000002) || caps[0] != (patched ? 7u : 0xdeadbeefu)
            || caps[1] != 0x12345678) return 1;
    q.type = 13; caps[0] = 0xdeadbeef;
    if ((UINT)query(&q) != 0xc0000002 || caps[0] != 0xdeadbeef) return 2;
    if ((UINT)query(NULL) != 0xc000000d) return 3;
    q.type = 70; q.size = 3;
    if ((UINT)query(&q) != (patched ? 0xc000000d : 0xc0000002) || caps[0] != 0xdeadbeef) return 4;
    q.size = 4; q.data = NULL;
    if ((UINT)query(&q) != (patched ? 0xc000000d : 0xc0000002)) return 5;
    q.data = caps; q.handle = 0;
    if ((UINT)query(&q) != (patched ? 0xc000000d : 0xc0000002)) return 6;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "stock") && strcmp(argv[1], "fg2x"))) return 10;
    int patched = !strcmp(argv[1], "fg2x");
    HMODULE gdi = LoadLibraryA("gdi32.dll");
    EnumFn enumerate = (EnumFn)GetProcAddress(gdi, "D3DKMTEnumAdapters2");
    QueryFn query = (QueryFn)GetProcAddress(gdi, "D3DKMTQueryAdapterInfo");
    CloseFn close = (CloseFn)GetProcAddress(gdi, "D3DKMTCloseAdapter");
    if (!enumerate || !query || !close) return 11;
    Adapter adapters[8] = {0}; EnumAdapters list = {8, adapters};
    LONG status = enumerate(&list);
    printf("HAGS enumerate=%08lx count=%lu\n", (unsigned long)status, list.count);
    if (status < 0 || !list.count || list.count > 8) return 12;
    int failed = 0;
    for (ULONG i = 0; i < list.count; ++i) {
        failed |= check(query, adapters[i].handle, patched, "dynamic");
        failed |= check(D3DKMTQueryAdapterInfo, adapters[i].handle, patched, "direct-import");
        close(&adapters[i].handle);
    }
    puts(failed ? "HAGS FAIL" : "HAGS PASS: valid/invalid queries, buffer boundary, other query, both import paths");
    return failed ? 13 : 0;
}
