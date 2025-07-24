import json

with open('./Toyota Oil v5.json', 'r') as f:
    data = json.load(f)
    engine_types = [f"{d['Number of Cylinders'] } {d['Is SUV']} {d['Engine Type']}" for d in data]
    set_engine_types = list(set(engine_types))

    print(set_engine_types)
    print(len(set_engine_types))