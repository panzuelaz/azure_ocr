select id,odometer,number,startDate from evaEvaluation
where deleted_at is null
and date(uploadedAt) = date(now())
and verifiedAt is null
and number > 0
and systemProcessedAt is null
and odometer > 0

and (evaEvaluation.cpnAssign_id, evaEvaluation.number) not in (
	select cpnAssign_id, max(number) from evaEvaluation
    where deleted_at is null
    group by 1
)