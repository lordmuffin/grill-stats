-- Redis monitoring script for Grill Stats application
-- This script exports additional metrics specific to the application

-- Return values for Prometheus
local result = {}

-- Cache metrics
local function cache_metrics()
  local metrics = {}

  -- Get cache hit/miss ratio
  local hits = redis.call('INFO', 'stats').keyspace_hits
  local misses = redis.call('INFO', 'stats').keyspace_misses
  local hit_rate = hits / (hits + misses)

  metrics.cache_hit_rate = hit_rate

  -- Get cache size by prefix
  local temp_cache_keys = #redis.call('KEYS', 'temperature:*')
  local device_cache_keys = #redis.call('KEYS', 'device:*')
  local session_cache_keys = #redis.call('KEYS', 'session:*')

  metrics.temperature_cache_size = temp_cache_keys
  metrics.device_cache_size = device_cache_keys
  metrics.session_cache_size = session_cache_keys

  return metrics
end

-- Pub/Sub metrics
local function pubsub_metrics()
  local metrics = {}

  -- Get number of channels and subscribers
  local pubsub_info = redis.call('PUBSUB', 'CHANNELS')
  metrics.pubsub_channels = #pubsub_info

  -- Get number of subscribers per key channel
  local temp_subs = redis.call('PUBSUB', 'NUMSUB', 'temperature_updates')
  local device_subs = redis.call('PUBSUB', 'NUMSUB', 'device_updates')
  local alert_subs = redis.call('PUBSUB', 'NUMSUB', 'temperature_alerts')

  metrics.temperature_subscribers = temp_subs[2]
  metrics.device_subscribers = device_subs[2]
  metrics.alert_subscribers = alert_subs[2]

  return metrics
end

-- Queue metrics
local function queue_metrics()
  local metrics = {}

  -- Get queue lengths
  local sync_queue = #redis.call('LRANGE', 'queue:sync', 0, -1)
  local notification_queue = #redis.call('LRANGE', 'queue:notifications', 0, -1)
  local processing_queue = #redis.call('LRANGE', 'queue:processing', 0, -1)

  metrics.sync_queue_length = sync_queue
  metrics.notification_queue_length = notification_queue
  metrics.processing_queue_length = processing_queue

  return metrics
end

-- Collect all metrics
local cache = cache_metrics()
local pubsub = pubsub_metrics()
local queue = queue_metrics()

-- Build result
for k, v in pairs(cache) do
  result["cache_" .. k] = v
end

for k, v in pairs(pubsub) do
  result["pubsub_" .. k] = v
end

for k, v in pairs(queue) do
  result["queue_" .. k] = v
end

return cjson.encode(result)
