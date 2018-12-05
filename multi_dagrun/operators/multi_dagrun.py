from airflow import settings
from airflow.models import DagBag
from airflow.operators.dagrun_operator import DagRunOrder, TriggerDagRunOperator
from airflow.utils import timezone
from airflow.utils.decorators import apply_defaults
from airflow.utils.state import State
from airflow.utils import timezone


class TriggerMultiDagRunOperator(TriggerDagRunOperator):
    CREATED_DAGRUN_KEY = 'created_dagrun_key'

    @apply_defaults
    def __init__(self, op_args=None, op_kwargs=None,
                 *args, **kwargs):
        super(TriggerMultiDagRunOperator, self).__init__(*args, **kwargs)
        self.op_args = op_args or []
        self.op_kwargs = op_kwargs or {}

    def execute(self, context):
        context.update(self.op_kwargs)
        session = settings.Session()
        created_dr_ids = []
        for dro in self.python_callable(*self.op_args, **context):
            if not dro:
                break
            if not isinstance(dro, DagRunOrder):
                dro = DagRunOrder(payload=dro)

            now = timezone.utcnow()
            if dro.run_id is None:
                dro.run_id = 'trig__' + now.isoformat()

            dbag = DagBag(settings.DAGS_FOLDER)
            trigger_dag = dbag.get_dag(self.trigger_dag_id)
            dr = trigger_dag.create_dagrun(
                run_id=dro.run_id,
                execution_date=now,
                state=State.RUNNING,
                conf=dro.payload,
                external_trigger=True,
            )
            created_dr_ids.append(dr.id)
            self.log.info("Created DagRun %s, %s", dr, now)

        if created_dr_ids:
            session.commit()
            context['ti'].xcom_push(self.CREATED_DAGRUN_KEY, created_dr_ids)
        else:
            self.log.info("No DagRun created")
        session.close()
