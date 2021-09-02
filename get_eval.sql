select id,odometer,number,startDate from evaEvaluation
where deleted_at is null
and date(DATE_ADD(uploadedAt, INTERVAL 7 HOUR)) = date(DATE_ADD(now(), INTERVAL 7 HOUR))
and verifiedAt is null
and number > 0
#and systemProcessedAt is null
and odometer > 0
and id = 3535278  #3538191    #3537045 #3535278

and (evaEvaluation.cpnAssign_id, evaEvaluation.number) not in (
        select cpnAssign_id, max(number) from evaEvaluation
    where deleted_at is null
    group by 1
)