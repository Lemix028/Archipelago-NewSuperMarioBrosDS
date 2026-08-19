-- =============================================================================
-- lua/nsmbds/memory.lua
-- Memory domain resolution, address translation, and byte/word manipulation
-- =============================================================================

local M = {
    domain = "Main RAM",
    sys_bus_domain = nil,
}

function M.is_rom_loaded()
    if emulation and emulation.getsystemid then
        local sysid = emulation.getsystemid()
        if sysid == "Null" or sysid == "NULL" or sysid == "" or sysid == nil then
            return false
        end
        return true
    end
    if gameinfo and gameinfo.getromname then
        local name = gameinfo.getromname()
        if name == "Null" or name == "NullHawk" or name == "" or name == nil then
            return false
        end
        return true
    end
    local ok, domains = pcall(memory.getmemorydomainlist)
    return ok and domains ~= nil and #domains > 0
end

function M.detect_memory_domain()
    local ok, domains = pcall(memory.getmemorydomainlist)
    if not ok or not domains or #domains == 0 then return "Main RAM" end
    local preferred = { "Main RAM", "ARM9 System Bus", "System Bus", "ARM9 RAM", "RAM" }
    for _, preferred_name in ipairs(preferred) do
        for _, domain_name in ipairs(domains) do
            if domain_name == preferred_name then return domain_name end
        end
    end
    return domains[1]
end

function M.detect_system_bus_domain()
    local ok, domains = pcall(memory.getmemorydomainlist)
    if not ok or not domains then return nil end
    for _, name in ipairs(domains) do
        if name == "ARM9 System Bus" or name == "System Bus" then return name end
    end
    return nil
end

function M.to_domain_addr(sys_addr)
    if M.domain == "Main RAM" then
        return sys_addr - 0x02000000
    end
    return sys_addr
end

function M.read_arm9_register(name)
    if not emu or not emu.getregister then return nil end
    local candidates = { name, string.lower(name), "ARM9 " .. name }
    for _, candidate in ipairs(candidates) do
        local ok, value = pcall(emu.getregister, candidate)
        if ok and type(value) == "number" then
            return value
        end
    end
    return nil
end

function M.clear_byte_flag(byte_val, flag_mask)
    return math.floor(byte_val) % (flag_mask * 2) >= flag_mask
        and (byte_val - flag_mask)
        or byte_val
end

function M.swap_word_flags(word_val, mask_a, mask_b)
    local has_a = math.floor(word_val / mask_a) % 2 >= 1
    local has_b = math.floor(word_val / mask_b) % 2 >= 1
    local result = word_val
    if has_a ~= has_b then
        if has_a then
            result = result - mask_a + mask_b
        else
            result = result - mask_b + mask_a
        end
    end
    return result
end

function M.read_byte_guarded(sys_addr)
    local addr = M.to_domain_addr(sys_addr)
    local ok, val = pcall(memory.readbyte, addr, M.domain)
    if ok and val then return val end
    return 0
end

function M.write_byte_guarded(sys_addr, val)
    local addr = M.to_domain_addr(sys_addr)
    pcall(memory.writebyte, addr, val, M.domain)
end

return M
