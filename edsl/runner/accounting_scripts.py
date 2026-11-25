"""Atomic Redis accounting for replayed distributed completion callbacks.

Validate inputs before mutations: Redis scripts are isolated but do not roll
back writes if a later command raises an error.
"""

INCREMENT_ONCE = """
local seen = redis.call('SISMEMBER', KEYS[2], ARGV[1])
if seen == 1 then return 0 end
local raw = redis.call('GET', KEYS[1])
local value = raw and cjson.decode(raw) or {_type='int', _value=0}
if value._type ~= 'int' or type(value._value) ~= 'number' then
    return redis.error_reply('invalid accounting counter')
end
redis.call('SET', KEYS[1], cjson.encode({_type='int', _value=value._value + 1}))
redis.call('SADD', KEYS[2], ARGV[1])
return 1
"""

GET_OR_SET = """
local existing = redis.call('GET', KEYS[1])
if existing then return existing end
redis.call('SET', KEYS[1], ARGV[1])
return ARGV[1]
"""

SATISFY_DEPENDENCY_ONCE = """
if redis.call('SISMEMBER', KEYS[2], ARGV[1]) == 1 then return 0 end
local raw = redis.call('GET', KEYS[1])
local value = raw and cjson.decode(raw)
if not value or value._type ~= 'int' or type(value._value) ~= 'number'
    or value._value < 1 then
    return redis.error_reply('missing or exhausted dependency counter')
end
local raw_status = redis.call('GET', KEYS[3])
local status = raw_status and cjson.decode(raw_status)
local queue_type = redis.call('TYPE', KEYS[4]).ok
if queue_type ~= 'none' and queue_type ~= 'set' then
    return redis.error_reply('invalid ready task set')
end
local remaining = value._value - 1
redis.call('SET', KEYS[1], cjson.encode({_type='int', _value=remaining}))
redis.call('SADD', KEYS[2], ARGV[1])
if remaining == 0 and status and status._value == 'pending' then
    redis.call('SET', KEYS[3], cjson.encode({_type='str', _value='ready'}))
    redis.call('SADD', KEYS[4], ARGV[2])
    return 1
end
return 0
"""
