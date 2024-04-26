
def get_enum_by_name(enum_class, name):
    for enum_member in enum_class:
        if enum_member.name == name:
            return enum_member
    raise ValueError(f"No enum member with value {name}")

def get_enum_by_value(enum_class, value):
    for enum_member in enum_class:
        if enum_member.value == value:
            return enum_member
    raise ValueError(f"No enum member with value {value}")