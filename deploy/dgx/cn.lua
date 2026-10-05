-- container 元数据提取 v2（05 Runbook §2.4 · 2026-10-05）
-- container_id：从 Path_Key(_src) 截取 12 位短 ID
-- container_name：读 container_map.tsv（id12→name，宿主 systemd timer 每 5 分钟刷新）
-- 映射表每 300s 重载一次（os.time 全局计时，进程级缓存）
local map = {}
local map_loaded_at = 0

local function load_map()
    local f = io.open("/fluent-bit/etc/container_map.tsv", "r")
    if not f then
        map_loaded_at = os.time() -- 无文件也计时，避免每条日志重试 IO
        return
    end
    local m = {}
    for line in f:lines() do
        local id, name = line:match("^([0-9a-f]+)%s+(.+)$")
        if id and name then
            m[string.sub(id, 1, 12)] = name
        end
    end
    f:close()
    map = m
    map_loaded_at = os.time()
end

function extract(tag, timestamp, record)
    if os.time() - map_loaded_at > 300 then
        load_map()
    end
    local src = record["_src"] or ""
    local id = src:match("containers/([0-9a-f]+)")
    if id and #id >= 12 then
        local short = string.sub(id, 1, 12)
        record["container_id"] = short
        record["container_name"] = map[short] or short
    end
    return 1, timestamp, record
end
