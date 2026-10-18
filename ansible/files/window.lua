-- Atomic rolling-hour admission by trusted account + MTA queue-id.
-- Uses Redis TIME, not a timestamp supplied by the email client.
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local token = ARGV[3]
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZSCORE', KEYS[1], token) then
  return {1, redis.call('ZCARD', KEYS[1]), 1}
end
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then return {0, count, 0} end
redis.call('ZADD', KEYS[1], now, token)
redis.call('PEXPIRE', KEYS[1], window + 60000)
return {1, count + 1, 0}
