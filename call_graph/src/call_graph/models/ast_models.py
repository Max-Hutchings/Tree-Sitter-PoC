# --- Data models for our index ----------------------------------------------
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MethodCall:
    """Represents a method call found inside a method body."""
    name: str  # simple method name being called (e.g., "save", "println")
    receiver: Optional[str]  # text of the call's receiver/object if present (e.g., "this.repo", "System.out")
    line: int
    col: int


@dataclass
class MethodInfo:
    """Information about a method declaration in a class."""
    name: str  # e.g., "addUser"
    params: list[str]  # param type/name strings (lightweight)
    return_type: Optional[str]  # simple textual return type (if found)
    line: int
    col: int
    calls: list[MethodCall] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a class in a package."""
    simple_name: str  # e.g., "UserService"
    fqcn: str  # fully-qualified class name, e.g., "com.acme.UserService"
    line: int
    col: int
    methods: dict[str, list[MethodInfo]] = field(default_factory=dict)  # name -> [overloads]