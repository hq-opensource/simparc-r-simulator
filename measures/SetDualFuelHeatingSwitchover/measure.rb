# frozen_string_literal: true

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/

# start the measure
class SetDualFuelHeatingSwitchover < OpenStudio::Measure::ModelMeasure
  # human readable name
  def name
    return 'Set Dual-Fuel Heating Switchover'
  end

  # human readable description
  def description
    return 'Overrides the sequential heating fraction schedules of the two heating systems with outdoor-temperature-driven schedules so heating is dispatched as a bi-energy (dual-fuel) switchover: system 1 (primary) serves the entire load above the switchover temperature and system 2 (auxiliary) serves the entire load below it. Both systems are assumed to be sized to the full design load (see building.py). Sizing is left untouched.'
  end

  # human readable description of modeling approach
  def modeler_description
    return 'Runs after HPXMLtoOpenStudio (post-sizing). Reads the building EPW (path passed as an argument, or the model weather file as a fallback) and builds two hourly fraction schedules from the outdoor drybulb temperature: primary = 1.0 when T_odb >= switchover_temp else 0.0, auxiliary = 1.0 - primary. For each conditioned zone that has two heating participants (identified in heating-priority order), replaces the primary and auxiliary sequential heating fraction schedules with these two schedules. No EMS and no HPXML schema change are used.'
  end

  # Define the arguments that the user will input.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @return [OpenStudio::Measure::OSArgumentVector] an OpenStudio::Measure::OSArgumentVector object
  def arguments(model) # rubocop:disable Lint/UnusedMethodArgument
    args = OpenStudio::Measure::OSArgumentVector.new

    arg = OpenStudio::Measure::OSArgument.makeBoolArgument('enabled', false)
    arg.setDisplayName('Enable Dual-Fuel Switchover')
    arg.setDescription('If true, overrides sequential heating fraction schedules with the temperature switchover. If false, the measure does nothing (stock behavior is preserved).')
    arg.setDefaultValue(true)
    args << arg

    arg = OpenStudio::Measure::OSArgument.makeDoubleArgument('switchover_temp', false)
    arg.setDisplayName('Switchover Temperature')
    arg.setDescription('Outdoor drybulb temperature (deg C) at/above which the primary system (system 1) serves the entire load; below it the auxiliary system (system 2) serves the entire load.')
    arg.setUnits('C')
    arg.setDefaultValue(-12.0)
    args << arg

    arg = OpenStudio::Measure::OSArgument.makeStringArgument('epw_path', false)
    arg.setDisplayName('EPW File Path')
    arg.setDescription('Absolute path to the EPW weather file used to build the switchover schedule. If empty, the model weather file is used.')
    arg.setDefaultValue('')
    args << arg

    return args
  end

  # Define what happens when the measure is run.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @param runner [OpenStudio::Measure::OSRunner] Object typically used to display warnings
  # @param user_arguments [OpenStudio::Measure::OSArgumentMap] OpenStudio measure arguments
  # @return [Boolean] true if successful
  def run(model, runner, user_arguments)
    super(model, runner, user_arguments)

    # use the built-in error checking
    if !runner.validateUserArguments(arguments(model), user_arguments)
      return false
    end

    enabled = runner.getBoolArgumentValue('enabled', user_arguments)
    unless enabled
      runner.registerAsNotApplicable('Dual-fuel switchover disabled; leaving sequential heating fraction schedules unchanged.')
      return true
    end

    switchover_temp = runner.getDoubleArgumentValue('switchover_temp', user_arguments)
    epw_path = runner.getStringArgumentValue('epw_path', user_arguments)

    # Resolve the EPW path (argument takes precedence, otherwise the model weather file).
    if epw_path.nil? || epw_path.strip.empty?
      if model.weatherFile.is_initialized && model.weatherFile.get.path.is_initialized
        epw_path = model.weatherFile.get.path.get.to_s
      else
        runner.registerError('No EPW path provided and the model has no weather file; cannot build the switchover schedule.')
        return false
      end
    end
    unless File.exist?(epw_path)
      runner.registerError("EPW file not found at '#{epw_path}'.")
      return false
    end

    # Read the hourly outdoor drybulb temperatures (deg C) from the EPW.
    epw_file = OpenStudio::EpwFile.new(epw_path, true)
    drybulbs_c = []
    epw_file.data.each_with_index do |epwdata, rownum|
      db = epwdata.dryBulbTemperature
      unless db.is_initialized
        runner.registerError("Cannot retrieve dry-bulb temperature from the EPW for record #{rownum + 1}.")
        return false
      end
      drybulbs_c << db.get
    end

    n_records = drybulbs_c.length
    if n_records < 8760
      runner.registerError("EPW contains only #{n_records} records; expected at least 8760 hourly values.")
      return false
    end

    # Build the two hourly fraction arrays. Primary (system 1) is on at/above the
    # switchover temperature; auxiliary (system 2) is on below it (strict complement).
    primary_fracs = drybulbs_c.map { |t| t >= switchover_temp ? 1.0 : 0.0 }
    auxiliary_fracs = primary_fracs.map { |f| 1.0 - f }

    # Fraction (0-1) schedule type limits, reused for both schedules.
    type_limits = OpenStudio::Model::ScheduleTypeLimits.new(model)
    type_limits.setName('Dual Switchover Fraction')
    type_limits.setLowerLimitValue(0.0)
    type_limits.setUpperLimitValue(1.0)
    type_limits.setNumericType('Continuous')
    type_limits.setUnitType('Dimensionless')

    # Interval schedules over the model calendar year, one value per EPW record.
    year_desc = model.getYearDescription
    year = year_desc.calendarYear.is_initialized ? year_desc.calendarYear.get : year_desc.assumedYear
    start_date = OpenStudio::Date.new(OpenStudio::MonthOfYear.new(1), 1, year)
    interval = OpenStudio::Time.new(0, 1, 0, 0) # 1 hour (days, hours, minutes, seconds)

    primary_sch = build_interval_schedule(model, start_date, interval, primary_fracs,
                                           'Dual-Fuel Primary Heating Fraction Schedule', type_limits, runner)
    return false if primary_sch.nil?

    auxiliary_sch = build_interval_schedule(model, start_date, interval, auxiliary_fracs,
                                            'Dual-Fuel Auxiliary Heating Fraction Schedule', type_limits, runner)
    return false if auxiliary_sch.nil?

    # Assign the schedules to the two heating systems in each conditioned zone.
    # Heating participants are taken in heating-priority order, so index 0 is
    # system 1 (primary, EnergyPlus heating sequence 1) and index 1 is system 2
    # (auxiliary, heating sequence 2). Matching by sequence rather than HPXML_ID is
    # robust for ducted systems, where the sequential schedule is owned by the air
    # terminal (which carries no HPXML_ID).
    n_zones_applied = 0
    model.getThermalZones.each do |zone|
      heating_equip = zone.equipmentInHeatingOrder.select do |equip|
        !zone.sequentialHeatingFractionSchedule(equip).empty?
      end
      next if heating_equip.empty?

      if heating_equip.length < 2
        runner.registerError("Dual-fuel switchover requires two heating systems in zone '#{zone.name}', but found #{heating_equip.length}. Ensure both heating_system and heating_system_2 are defined.")
        return false
      end
      if heating_equip.length > 2
        runner.registerWarning("Zone '#{zone.name}' has #{heating_equip.length} heating participants; applying the switchover to the first two in heating order and leaving the rest unchanged.")
      end

      primary_equip = heating_equip[0]
      auxiliary_equip = heating_equip[1]

      unless zone.setSequentialHeatingFractionSchedule(primary_equip, primary_sch)
        runner.registerError("Failed to set the primary sequential heating fraction schedule in zone '#{zone.name}'.")
        return false
      end
      unless zone.setSequentialHeatingFractionSchedule(auxiliary_equip, auxiliary_sch)
        runner.registerError("Failed to set the auxiliary sequential heating fraction schedule in zone '#{zone.name}'.")
        return false
      end

      runner.registerInfo("Applied dual-fuel switchover at #{switchover_temp.round(2)} C in zone '#{zone.name}': primary='#{primary_equip.name}', auxiliary='#{auxiliary_equip.name}'.")
      n_zones_applied += 1
    end

    if n_zones_applied == 0
      runner.registerAsNotApplicable('No zone with heating equipment and a sequential heating fraction schedule was found; nothing to override.')
      return true
    end

    n_below = auxiliary_fracs.count { |f| f > 0.5 }
    runner.registerFinalCondition("Applied dual-fuel temperature switchover to #{n_zones_applied} zone(s) at #{switchover_temp.round(2)} C; auxiliary (system 2) is active for #{n_below} of #{n_records} hours.")
    return true
  end

  # Builds an interval fraction schedule from an array of hourly values.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @param start_date [OpenStudio::Date] Schedule start date (Jan 1 of the model year)
  # @param interval [OpenStudio::Time] Interval between values (1 hour)
  # @param values [Array<Double>] Hourly fraction values
  # @param sch_name [String] Name for the created schedule
  # @param type_limits [OpenStudio::Model::ScheduleTypeLimits] Fraction type limits
  # @param runner [OpenStudio::Measure::OSRunner] Object used to display errors
  # @return [OpenStudio::Model::ScheduleInterval, nil] The schedule, or nil on failure
  def build_interval_schedule(model, start_date, interval, values, sch_name, type_limits, runner)
    time_series = OpenStudio::TimeSeries.new(start_date, interval, OpenStudio::createVector(values), '')
    sch_opt = OpenStudio::Model::ScheduleInterval.fromTimeSeries(time_series, model)
    unless sch_opt.is_initialized
      runner.registerError("Failed to create interval schedule '#{sch_name}' from the EPW time series.")
      return nil
    end
    sch = sch_opt.get
    sch.setName(sch_name)
    sch.setScheduleTypeLimits(type_limits)
    return sch
  end
end

# register the measure to be used by the application
SetDualFuelHeatingSwitchover.new.registerWithApplication
