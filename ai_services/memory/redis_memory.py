class InMemoryRedis:
    def __init__(self): self.data = {}
    def rpush(self, key, value): self.data.setdefault(key, []).append(value)
    def lrange(self, key, start, end):
        values = self.data.get(key, [])
        return values[start:] if end == -1 else values[start:end + 1]
    def lpop(self, key): return self.data.get(key, []).pop(0) if self.data.get(key) else None
    def get(self, key): return self.data.get(key)
    def set(self, key, value): self.data[key] = value
    def delete(self, key): self.data.pop(key, None)
