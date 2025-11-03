from tests import patch_agent
patch_agent.install_usage_collector()



def pytest_sessionfinish(session, exitstatus):
    from tests import patch_agent
    patch_agent.print_report_usage()