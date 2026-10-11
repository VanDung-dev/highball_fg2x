#include <windows.h>
#include <dxgi.h>
#include <stdio.h>
#include "vendor/streamline/sl.h"

using InitFn = sl::Result (*)(const sl::Preferences &, uint64_t);
using SupportedFn = sl::Result (*)(sl::Feature, const sl::AdapterInfo &);
using ShutdownFn = sl::Result (*)();
using FactoryFn = HRESULT (WINAPI *)(REFIID, void **);

static void logMessage(sl::LogType type, const char *message) {
    printf("SL LOG type=%u %s\n", (unsigned)type, message);
}

int main(int argc, char **argv) {
    if (argc != 2) { puts("Usage: streamline_probe.exe <Windows path to SDK plugin directory>"); return 1; }
    wchar_t plugins[4096] = {}, dll[4096] = {};
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, argv[1], -1, plugins, 4000)) return 2;
    wcscpy(dll, plugins); wcscat(dll, L"\\sl.interposer.dll");
    DWORD handle = 0, size = GetFileVersionInfoSizeW(dll, &handle);
    unsigned char versionData[16384] = {};
    VS_FIXEDFILEINFO *version = nullptr; UINT versionSize = 0;
    if (!size || size > sizeof(versionData) || !GetFileVersionInfoW(dll, 0, size, versionData)
            || !VerQueryValueW(versionData, L"\\", (void **)&version, &versionSize)) return 3;
    unsigned major = HIWORD(version->dwFileVersionMS), minor = LOWORD(version->dwFileVersionMS), patch = HIWORD(version->dwFileVersionLS);
    uint64_t sdk = (uint64_t(major) << 48) | (uint64_t(minor) << 32) | (uint64_t(patch) << 16) | sl::kSDKVersionMagic;
    printf("SL DLL version=%u.%u.%u\n", major, minor, patch);
    HMODULE module = LoadLibraryW(dll);
    if (!module) { printf("SL LoadLibrary error=%lu\n", GetLastError()); return 4; }
    InitFn init = (InitFn)GetProcAddress(module, "slInit");
    SupportedFn supported = (SupportedFn)GetProcAddress(module, "slIsFeatureSupported");
    ShutdownFn shutdown = (ShutdownFn)GetProcAddress(module, "slShutdown");
    if (!init || !supported || !shutdown) return 5;
    sl::Feature features[] = {sl::kFeatureDLSS_G, sl::kFeatureReflex};
    const wchar_t *pluginPaths[] = {plugins};
    CreateDirectoryW(L"C:\\sl-probe-logs", nullptr);
    sl::Preferences preferences;
    preferences.pathsToPlugins = pluginPaths;
    preferences.numPathsToPlugins = 1;
    preferences.pathToLogsAndData = L"C:\\sl-probe-logs";
    preferences.logLevel = sl::LogLevel::eVerbose;
    preferences.logMessageCallback = logMessage;
    preferences.flags = sl::PreferenceFlags::eDisableCLStateTracking | sl::PreferenceFlags::eUseManualHooking;
    preferences.featuresToLoad = features;
    preferences.numFeaturesToLoad = 2;
    preferences.engine = sl::EngineType::eCustom;
    preferences.engineVersion = "1.0";
    preferences.projectId = "00000000-0000-4000-8000-000000000001";
    sl::Result result = init(preferences, sdk);
    printf("SL Init result=%u\n", (unsigned)result);
    if (result != sl::Result::eOk) { shutdown(); return 6; }
    HMODULE dxgi = LoadLibraryA("dxgi.dll");
    FactoryFn create = dxgi ? (FactoryFn)GetProcAddress(dxgi, "CreateDXGIFactory1") : nullptr;
    const GUID iid = {0x770aae78, 0xf26f, 0x4dba, {0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87}};
    IDXGIFactory1 *factory = nullptr;
    int exitCode = 7;
    if (create && SUCCEEDED(create(iid, (void **)&factory))) {
        IDXGIAdapter1 *adapter = nullptr;
        if (SUCCEEDED(factory->EnumAdapters1(0, &adapter))) {
            DXGI_ADAPTER_DESC1 desc = {}; adapter->GetDesc1(&desc);
            sl::AdapterInfo info;
            info.deviceLUID = (uint8_t *)&desc.AdapterLuid;
            info.deviceLUIDSizeInBytes = sizeof(desc.AdapterLuid);
            exitCode = 0;
            for (sl::Feature feature : features) {
                result = supported(feature, info);
                printf("SL Feature=%u supported_result=%u\n", feature, (unsigned)result);
                if (result != sl::Result::eOk) exitCode = 8;
            }
            adapter->Release();
        }
        factory->Release();
    }
    result = shutdown();
    printf("SL Shutdown result=%u\n", (unsigned)result);
    return result == sl::Result::eOk ? exitCode : 9;
}
