-- Lightweight opt-in frame profiler. Enable before loading the runtime with:
--   NSMBDS_PERF_PROFILE = true
-- Optional report controls:
--   NSMBDS_PERF_REPORT_FRAMES = 600
--   NSMBDS_PERF_SPIKE_MS = 1.0
--   NSMBDS_PERF_FRAME_MS = 5.0
local M = {}

local clock = os and os.clock
local enabled = rawget(_G, "NSMBDS_PERF_PROFILE") == true
    and type(clock) == "function"
local threshold_ms = math.max(
    0,
    tonumber(rawget(_G, "NSMBDS_PERF_SPIKE_MS")) or 2.0
)
local total_threshold_ms = math.max(
    threshold_ms,
    tonumber(rawget(_G, "NSMBDS_PERF_FRAME_MS")) or 5.0
)
local report_frames = math.max(
    1,
    math.floor(tonumber(rawget(_G, "NSMBDS_PERF_REPORT_FRAMES")) or 600)
)
local frame = 0
local frame_started = nil
local interval_frames = 0
local last_total_spike_frame = -60
local totals = {}
local maxima = {}
local calls = {}

local function record(name, elapsed_ms)
    totals[name] = (totals[name] or 0) + elapsed_ms
    maxima[name] = math.max(maxima[name] or 0, elapsed_ms)
    calls[name] = (calls[name] or 0) + 1
end

local function report_interval()
    print(string.format("NSMBDS PERF summary frames=%d", interval_frames))
    local names = {}
    for name in pairs(calls) do names[#names + 1] = name end
    table.sort(names)
    for _, name in ipairs(names) do
        local count = calls[name]
        local average = totals[name] / math.max(1, count)
        local maximum = maxima[name]
        if totals[name] > 0 or maximum >= threshold_ms then
            print(string.format(
                "NSMBDS PERF section=%s avg=%.3fms max=%.3fms calls=%d",
                name,
                average,
                maximum,
                count
            ))
        end
    end
    totals = {}
    maxima = {}
    calls = {}
    interval_frames = 0
end

function M.is_enabled()
    return enabled
end

function M.begin_frame(value)
    if not enabled then return end
    frame = value or 0
    frame_started = clock()
end

function M.start_section()
    return enabled and clock() or nil
end

function M.finish_section(name, started)
    if not enabled or started == nil then return end
    record(name, (clock() - started) * 1000)
end

function M.end_frame()
    if not enabled or frame_started == nil then return end
    local elapsed_ms = (clock() - frame_started) * 1000
    frame_started = nil
    record("total", elapsed_ms)
    interval_frames = interval_frames + 1
    if elapsed_ms >= total_threshold_ms and frame - last_total_spike_frame >= 60 then
        last_total_spike_frame = frame
        print(string.format(
            "NSMBDS PERF SPIKE frame=%d total=%.3fms",
            frame,
            elapsed_ms
        ))
    end
    if interval_frames >= report_frames then report_interval() end
end

if enabled then
    print(string.format(
        "NSMBDS PERF enabled: report=%d frames section=%.3fms frame=%.3fms",
        report_frames,
        threshold_ms,
        total_threshold_ms
    ))
end

return M
