import json

from etcd import EtcdException
from etcd import EtcdKeyNotFound

from tendrl.commons.objects.alert import AlertUtils
from tendrl.commons.utils import log_utils as logger
from tendrl.node_agent.alert import constants
from tendrl.node_agent.alert import utils


class InvalidAlertType(Exception):
    pass


class InvalidAlertSeverity(Exception):
    pass


def update_alert(message):
    try:
        existing_alert = False
        new_alert = json.loads(message.payload["message"])
        new_alert['alert_id'] = message.message_id
        new_alert_obj = AlertUtils().to_obj(new_alert)
        if new_alert_obj.alert_type not in constants.SUPPORTED_ALERT_TYPES:
            logger.log(
                "error",
                NS.publisher_id,
                {
                    "message": "Invalid alert type in alert %s" % new_alert
                }
            )
            raise InvalidAlertType
        if new_alert_obj.severity not in constants.SUPPORTED_ALERT_SEVERITY:
            logger.log(
                "error",
                NS.publisher_id,
                {
                    "message": "Invalid alert severity in alert %s" % new_alert
                }
            )
            raise InvalidAlertSeverity
        alerts = utils.get_alerts(new_alert_obj)
        for curr_alert in alerts:
            curr_alert.tags = json.loads(curr_alert.tags)
            if AlertUtils().is_same(new_alert_obj, curr_alert):
                new_alert_obj = AlertUtils().update(
                    new_alert_obj,
                    curr_alert
                )
                if not AlertUtils().equals(
                    new_alert_obj,
                    curr_alert
                ):
                    existing_alert = True
                    utils.update_alert_count(
                        new_alert_obj,
                        existing_alert
                    )
                    if message.payload["alert_condition_unset"]:
                        keep_alive = int(
                            NS.config.data["alert_retention_time"]
                        )
                        utils.classify_alert(new_alert_obj, keep_alive)
                        new_alert_obj.save(ttl=keep_alive)
                    else:
                        # Remove the clearing alert with same if exist
                        utils.remove_alert(new_alert_obj)
                        utils.classify_alert(new_alert_obj)
                        new_alert_obj.save()
                    return
                return
            # else add this new alert to etcd
        if message.payload["alert_condition_state"] == \
            constants.ALERT_SEVERITY["warning"]: 
            utils.update_alert_count(
                new_alert_obj,
                existing_alert
            )
            utils.classify_alert(new_alert_obj)
            new_alert_obj.save()
        else:
            logger.log(
                "error",
                NS.publisher_id,
                {
                    "message": "New alert can't be a clearing alert %s" % (
                        new_alert
                    )
                }
            )
    except(
        AttributeError,
        TypeError,
        ValueError,
        KeyError,
        InvalidAlertType,
        InvalidAlertSeverity,
        EtcdKeyNotFound,
        EtcdException
    ) as ex:
        logger.log(
            "error",
            NS.publisher_id,
            {
                "message": "Error %s in updating alert %s" % (
                    ex, new_alert
                )
            }
        )
