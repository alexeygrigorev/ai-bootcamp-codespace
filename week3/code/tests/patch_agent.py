
from functools import wraps
import inspect
from typing import Any

# Don't import pydantic_ai types here

# Central in-process collector
_USAGE_RECORDS = {}


def _record_usage_from_result(agent, result):
    try:
        model_name = agent.model.model_name
        usage = result.usage()

        if usage is None:
            return

        if model_name not in _USAGE_RECORDS:
            _USAGE_RECORDS[model_name] = []
        _USAGE_RECORDS[model_name].append(usage)
    except Exception:
        return


def _wrap_run_callable(orig_run):
    """Return an async wrapper which calls orig_run and records usage."""

    @wraps(orig_run)
    async def wrapped(self, *args, **kwargs):
        result = await orig_run(self, *args, **kwargs)
        try:
            _record_usage_from_result(self, result)
        except Exception:
            pass
        return result

    return wrapped


def install_usage_collector() -> bool:
    installed = False
    
    from pydantic_ai import Agent as PAAgent  # type: ignore

    try:
        if not hasattr(PAAgent, "_orig_run_for_tests"):
            orig_run = getattr(PAAgent, "run", None)
            setattr(PAAgent, "_orig_run_for_tests", orig_run)
            if orig_run is not None and inspect.iscoroutinefunction(orig_run):
                PAAgent.run = _wrap_run_callable(orig_run)
            installed = True
    except Exception:
        pass

    return installed


def get_usage_aggregated():
    from pydantic_ai import RunUsage  # type: ignore

    aggregated = {}

    for model_name, usage_list in _USAGE_RECORDS.items():
        total = RunUsage()

        for usage in usage_list:
            total.incr(usage)

        aggregated[model_name] = total

    return aggregated


def print_report_usage() -> Any:
    from toyaikit.pricing import PricingConfig
    pricing = PricingConfig()
    print('\n=== USAGE REPORT ===')

    aggregated = get_usage_aggregated()

    for model_name, usage in aggregated.items():
        cost = pricing.calculate_cost(
            model=model_name,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens
        )
        print(f'Model: {model_name}, Cost: {cost}')

    print('====================\n')