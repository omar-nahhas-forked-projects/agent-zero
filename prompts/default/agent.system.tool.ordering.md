### Tool Ordering:
tools execute sequentially one at a time
express dependencies in thoughts
process each result before next tool

1. Plan First:
~~~json
{
    "thoughts": [
        "Complete plan with all required tools",
        "Tool1 needed for initial data",
        "Tool2 depends on Tool1 result",
        "Tool3 will use both results"
    ]
}
~~~

2. Request Tools in Sequence:
~~~json
{
    "thoughts": [
        "Starting with Tool1",
        "Need its output for Tool2"
    ],
    "tool_name": "tool1",
    "tool_args": {
        "arg1": "value1"
    }
}
~~~

3. Process Results:
~~~json
{
    "thoughts": [
        "Tool1 returned: ...",
        "Using this output for Tool2"
    ],
    "tool_name": "tool2",
    "tool_args": {
        "arg1": "value from tool1"
    }
}
~~~

4. Complete Chain:
~~~json
{
    "thoughts": [
        "All prerequisite data gathered",
        "Executing final tool"
    ],
    "tool_name": "tool3",
    "tool_args": {
        "arg1": "combined results"
    }
}
~~~
