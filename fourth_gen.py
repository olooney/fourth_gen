import json as jsonlib
import os
import inspect
import dis
import re
import time
import functools
from typing import Callable, List, Dict, Tuple

def function_body_is_empty(f: Callable) -> bool:
    """
    Use bytecode to detect if a function body is truely empty (e.g.,
    contains only `pass` or `...`.) This is probably a bad idea because
    the bytecode is not stable across versions, but this logic should
    work on Python 3.0 - 3.12.
    """
    try:
        # dis.Bytecode can handle, functions, methods, method wrappers, etc.
        bytecode = dis.Bytecode(f)
    except TypeError:
        # handle the case of callable objects as well.
        if hasattr(f, "__call__"):
            bytecode = dis.Bytecode(f.__call__)
        else:
            raise

    instructions = list(bytecode)

    # the longest empty function should be RESUME, LOAD_CONST, RETURN_VALUE.
    if len(instructions) > 3:
        return False

    # empty functions can only use a select few opcodes.
    for instruction in instructions:
        if instruction.opname in ["LOAD_CONST", "RETURN_CONST"]:
            # these instructions are OK if they have the None value.
            if instruction.argval is not None:
                return False
        elif instruction.opname in ["RESUME", "RETURN_VALUE"]:
            # these instructions are always OK
            pass
        else:
            # anything else suggests the function is doing real work
            return False

    return True


def format_function_call(function_name: str, args: List, kwargs: Dict) -> str:
    """
    Return the Python code used to call the named function with the given
    positional and keyword args. Assumes all args and kwargs values have a
    correct `repr()` representation.
    """
    formatted_args = [repr(a) for a in args]
    formatted_args += [ f"{k}={v!r}" for k, v in kwargs.items() ]
    args_string = ", ".join(formatted_args)
    return f"{function_name}({args_string})"


def format_function_spec(f: Callable) -> str:
    """
    Return the Python code used to declare a function with the
    same name, signature, and docstring as the function `f`.
    """
    signature = inspect.signature(f)

    if hasattr(f, "__name__") and f.__name__ != "<lambda>":
        function_name = f.__name__
    else:
        function_name = "f"
    
    if hasattr(f, "__doc__"):
        docstring = f.__doc__.replace('"""', "'''")
    else:
        docstring = ""
    return f'def {function_name}{signature}:\n    """{docstring}"""'


def extract_python_code(text: str) -> str:
    """
    GPT likes to return Python code inside a Markdown code block and also
    likes to add discussion or comments before or after the code block.
    This function extracts and returns the code portion only, disregarding
    commentary. It doesn't work if the LLM returns more than one code block.
    """
    code_block_match = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    if not code_block_match:
        raise ValueError("No valid Python code block found in the LLM response.")
    
    code = code_block_match.group(1).strip()
    return code


SYSTEM_MESSAGE = """
You are a skilled and capable coding assistant who helps users by providing 
correct, idiomatic, carefully designed implementations of Python functions from
nothing more than a function signature and natural language description. You
are also more then able to handle less well designed tasks (or those requiring
natural language processing) yourself on a case-by-case basis.
"""


DECISION_TEMPLATE = """
Decide if this function can be implemented in Python, or if it needs the more
flexible handling of an LLM:

```python
{spec}
```

The only valid styles are "flexible" or "rigid."

A "rigid" style function is algorithmic and procedural and can
be implemented in a straight-forward way in Python.

A "flexible" style function relies on natural language, text processing,
subjective judgement, or creativity. The tasks should be
handled by a human or delegated to an LLM.

Return your judgement as a JSON object in this format:

{{ "style": "flexible" }}

or 

{{ "style": "rigid" }}

"""


HANDLE_TEMPLATE = """
For this Python function:

```python
{spec}
```

What would be the best return value for this function call?

```python
{call}
```

Please your best judgement and return your answer as a JSON object
with under the "return_value" key:

{{ "return_value": "result" }}
"""


IMPLEMENT_TEMPLATE = """
Write a correct Python implementation of this function:

```python
{spec}
```
Return your result in a single code block. Do not provide an example of calling
the function. Do not run the function. You can explain your algorithm before
writing the function, but do not provide any explanation or examples after 
the function.
"""

HANDLE_ERROR_TEMPLATE = """
This function:

```python
{spec}
```

Was called with these arguments:

```python
{call}
```

Which raised this exception:

    {error}

Use your best judgment to return a JSON object which best
matches the type and correct value based on your understanding
of what the function was intended to do and what the user
meant by the arguments that were passed in. 

For example, if the function add(7, "5") raised a TypeError,
we can guess the user meant to pass add(7, 5) to obtain 12.

Return your answer in one of these JSON formats. If you
can infer a return value, use:

{{ "return_value": "result" }}

This should be your preferred option if you can reasonably
infer a return value.

If you feel the error was correct and unavoidable because
there simply isn't enough information to infer correct 
behavior, use:

{{ "error": "message" }}

"""

UNIT_TEST_TEMPLATE = """
Write a pytest style unit test function:

```python
def {test_function_name}({function_name}):
    ...
```

For this function:
```python
{spec}
```

The function itself will be passed into `{test_function_name}` at runtime,
so be sure to have it accept exactly one argument.

Make up reasonable test cases and write `assert` statements for each. Do
not return anything. When testing floating point math, use `pytest.approx`.
If the function is documented as raising or throwing an exception, use
`with pytest.raises` to test that. Do not test for exceptions that are
not explictly mentioned.

Include a short explanation of the error for every assert. Keep the code
minimal and clean.

Return your result in a single code block. Do not provide an example of calling
the function. Do not run the function. You can explain your algorithm before
writing the function, but do not provide any explanation or examples after 
the function.

"""


class CodingAssistant:
    """
    The 4th gen coding assistant provides decorators to automatically
    generate function implementations from docstrings, and help with
    a few other related tasks like testing.
    """
    def __init__(
        self, 
        openai_client,
        fast_model: str = 'gpt-4o-mini',
        smart_model: str = 'gpt-4-turbo',
        temperature=0.0
    ):
        self._client = openai_client
        self._fast_model = fast_model
        self._smart_model = smart_model
        self._temperature = float(temperature)
        self._log = []
        self._messages = self.system_messages()

    @classmethod
    def system_messages(cls):
        """
        Creates a new, fresh messages list containing only the initial
        system messages and few-shot examples.
        """
        return [
            {"role": "system", "content": SYSTEM_MESSAGE },
        ]

    def log(self, prompt, response, duration):
        """Adds a single prompt/response pair to the log.
        """
        log_entry = {
            "prompt": prompt,
            "message": response.choices[0].message,
            "model": response.model,
            "timestamp": response.created,
            "duration": duration,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }
        self._log.append(log_entry)

    @property
    def usage(self):
        """
        Returns a usage report over the lifetime of this agent instance showing
        the number of LLM requests, total duration spent waiting for requests to
        complete, the number of input and output tokens, and an estimate of total
        cost incurred.
        """
        def cost_of(log_entry: dict) -> float:
            if log_entry['model'].startswith('gpt-4o-mini'):
                return log_entry['input_tokens'] * 0.15e-6 + log_entry['output_tokens'] * 0.6e-6
            elif log_entry['model'].startswith('gpt-4-turbo'):
                return log_entry['input_tokens'] * 5e-6 + log_entry['output_tokens'] * 15e-6
            else:
                return -999

        usage_summary = {
            "requests": len(self._log),
            "duration": sum(le['duration'] for le in self._log),
            "output_tokens": sum(le['output_tokens'] for le in self._log),
            "input_tokens": sum(le['input_tokens'] for le in self._log),
            "cost": sum(cost_of(le) for le in self._log),
        }
        return usage_summary

    def chat(self, prompt, smart=False, json=False, isolate=False):
        """
        Make a request to an LLM. Handles timing and logging. By
        default, the prompt and response will be added to the session
        history; use `isolate=True` or call `.task()` instead to avoid
        this. Use `smart=True` to use a slower model better suited to
        complex code generation. Use `json=True` to request JSON and
        automatically deserialize the response.
        """
        # prepare messages
        if isolate:
            messages = self.system_messages()
        else:
            messages = self._messages
        messages.append({"role": "user", "content": prompt})

        # handle other options
        model = self._smart_model if smart else self._fast_model
        max_tokens = 4096 if smart else 8192

        # make the request
        start_time = time.time()
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self._temperature,
            max_completion_tokens=max_tokens,
            response_format={ "type": ("json_object" if json else "text") },
        )
        end_time = time.time()
        duration = end_time - start_time

        # log the results for later
        self.log(prompt, response, duration)
        self.most_recent_response = response

        # handle/format the response
        full_message = response.choices[0]
        if full_message.finish_reason == "stop":
            message = full_message.message.content
            messages.append({"role": "assistant", "content": message})
            if json:
                return jsonlib.loads(message)
            else:
                return message
        elif full_message.finish_reason == "length":
            raise Exception("LLM output exceeded maximum content length")
        else:
            raise Exception(f"Unknown finish_reason: {full_message.finish_reason!r}")

    def task(self, prompt, smart=False, json=False):
        """Run a single LLM prompt in isolation (no session history.)"""
        return self.chat(prompt, smart=smart, json=json, isolate=True)

    def handle(self, f):
        """
        Decorator which wraps an empty function with only a docstring and 
        handles it by always calling an LLM, passing the function call
        arguments and parsing the resulting JSON for a return value.
        """
        assert function_body_is_empty(f)

        # introspect the function
        name = f.__name__
        spec = format_function_spec(f)
        
        # create a wrapper which delegates each function call to the LLM.
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            call = format_function_call(name, args, kwargs)
            prompt = HANDLE_TEMPLATE.format(call=call, spec=spec)
            return self.task(prompt, json=True)['return_value']

        # add metadata
        wrapper.__fourth_gen_approach__ = 'flexible'

        return wrapper

    def implement(self, f):
        """
        Decorator which wraps an empty function with only a docstring and
        handles it by having an LLM generate Python code for the function,
        then invoking that code every time the function is called.
        """
        assert function_body_is_empty(f)

        # have the LLM write our code for us
        function_name = f.__name__
        spec = format_function_spec(f)
        prompt = IMPLEMENT_TEMPLATE.format(spec=spec)
        message = self.task(prompt, smart=True)
        code = extract_python_code(message)

        # execute the code locally to obtain a function reference
        frame = {}
        exec(code, frame)
        generated_function = frame[function_name]
        wrapper = functools.wraps(f)(generated_function)

        # add metadata
        wrapper.__fourth_gen_approach__ = 'rigid'
        wrapper.__fourth_gen_code__ = code
        
        return wrapper
        
    def write(self, f: Callable) -> Callable:
        """
        Decorator which wraps an empty function with only a docstring and
        implements it by delegating to either `.handle()` or `.implement()`.
        Which strategy is used depends on if the task requires flexible or
        rigid intelligence, and that decision itself is made by an LLM.
        """
        spec = format_function_spec(f)
        prompt = DECISION_TEMPLATE.format(spec=spec)
        style = self.task(prompt, json=True)['style']
        if style == 'rigid':
            return self.implement(f)
        elif style == 'flexible':
            return self.handle(f)
        else:
            raise ValueError(f"Unknown process style {style!r}")

    # convenience function to use the CodeAssistant itself as the decorator
    __call__ = write

    def handle_error(self, f: Callable) -> Callable:
        """
        Decorator which adds flexible error handling to any function. If
        an exception is thrown, the `CodingAssistant` will handle the 
        function call instead, taking in to account the arguments and error
        message.
        """
        name = f.__name__
        if hasattr(f, "__fourth_gen_code__"):
            spec = f.__fourth_gen_code__
        else:
            spec = format_function_spec(f)
        
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error = repr(e)

                # have the LLM handle the error
                call = format_function_call(name, args, kwargs)
                prompt = HANDLE_ERROR_TEMPLATE.format(
                    spec=spec,
                    call=call,
                    error=repr(e),
                )
    
                fix = self.task(prompt, json=True)
                if "return_value" in fix:
                    return fix["return_value"]
                else:
                    raise
                    
        return wrapper

    def write_unit_test(self, f: Callable) -> Callable:
        """
        Write a unit test for the given function. The unit test function is
        returned but not executed. 
        
        To write the unit tests and run them immediately, use `.test()`.
        """
        if function_body_is_empty(f):
            raise ValueError("Cannot test a function with empty body. Did you mean to use .write() instead?")

        function_name = f.__name__
        test_function_name = f"test_{function_name}"
        
        prompt = UNIT_TEST_TEMPLATE.format(
            test_function_name=test_function_name,
            function_name=function_name,
            spec=format_function_spec(f),
        )
        message = self.task(prompt, smart=True)
        code = extract_python_code(message)

        # execute the code locally to obtain a function reference
        frame = {}
        exec(code, frame)
        tester = frame[test_function_name]

        def test_function():
            tester(f)

        # add metadata
        test_function.__fourth_gen_approach__ = 'unit_test'
        test_function.__fourth_gen_code__ = code

        return test_function

