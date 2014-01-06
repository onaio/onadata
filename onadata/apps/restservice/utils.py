from onadata.apps.restservice.models import RestService


def call_service(parsed_instance):
    # lookup service
    instance = parsed_instance.instance
    services = RestService.objects.filter(xform=instance.xform)
    # call service send with url and data parameters
    for sv in services:
        # TODO: Queue service
        try:
            service = sv.get_service_definition()()
            service.send(sv.service_url, parsed_instance)
        except:
            # TODO: Handle gracefully | requeue/resend
            pass


def call_ziggy_services(ziggy_instance, uuid):
    # we can only handle f2dhis2 services at this time
    services = RestService.objects.filter(xform=ziggy_instance.xform,
                                          name='f2dhis2')
    services_called = 0
    for sv in services:
        # TODO: Queue service
        try:
            service = sv.get_service_definition()()
            response = service.send_ziggy(sv.service_url, ziggy_instance, uuid)
        except:
            # TODO: Handle gracefully | requeue/resend
            pass
        else:
            if response is not None and response.status_code == 200:
                services_called += 1
    return services_called
