#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

typedef struct { uint32_t handle, type; void *data; uint32_t size; } Query;
extern uint32_t fg2x_query(Query *);
_Static_assert(sizeof(Query) == 24, "Wine Unix query ABI");
_Static_assert(offsetof(Query, data) == 8 && offsetof(Query, size) == 16, "query offsets");

#define CHECK(condition) do { if (!(condition)) { printf("FAIL line %d\n", __LINE__); return 1; } } while (0)

int main(void) {
    uint32_t data[2] = {0xdeadbeef, 0x12345678};
    Query q = {1, 70, data, 4};
    CHECK(fg2x_query(&q) == 0 && data[0] == 7 && data[1] == 0x12345678);
    data[0] = 0xdeadbeef; q.type = 13;
    CHECK(fg2x_query(&q) == 0xc0000002 && data[0] == 0xdeadbeef);
    q.type = 70; q.size = 3;
    CHECK(fg2x_query(&q) == 0xc000000d && data[0] == 0xdeadbeef);
    q.size = 4; q.data = NULL;
    CHECK(fg2x_query(&q) == 0xc000000d);
    q.data = data; q.handle = 0;
    CHECK(fg2x_query(&q) == 0xc000000d && data[0] == 0xdeadbeef);
    CHECK(fg2x_query(NULL) == 0xc000000d);
    q.handle = 1; q.size = 8;
    CHECK(fg2x_query(&q) == 0 && data[0] == 7 && data[1] == 0x12345678);
    puts("PASS: assembled x86_64 payload, ABI, capability bits, invalid inputs, buffer boundary, unrelated query");
    return 0;
}
