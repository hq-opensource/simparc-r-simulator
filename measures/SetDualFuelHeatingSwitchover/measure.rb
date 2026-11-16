# frozen_string_literal: true

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/

# start the measure
class SetDualFuelHeatingSwitchover < OpenStudio::Measure::ModelMeasure
  PRIMARY_HPXML_ID = 'HeatingSystem1'
  AUXILIARY_HPXML_ID = 'HeatingSystem2'
  # HPXMLtoOpenStudio sizes a 0-fraction system to 1 Btu/h (~0.29 W); anything below
  # this threshold is treated as that placeholder and resized.
  PLACEHOLDER_CAPACITY_W = 10.0

  # human readable name
  def name
    return 'Set Dual-Fuel Heating Switchover'
  end

  # human readable description
  def description
    return 'Overrides the sequential heating fraction schedules of the two heating systems with outdoor-temperature-driven schedules so heating is dispatched as a bi-energy (dual-fuel) switchover: system 1 (primary) serves the entire load above the switchover temperature and system 2 (auxiliary) serves the entire load below it. Both systems are assumed to be sized to the full design load (see building.py). When two ducted furnaces share a distribution (HPXML split 1.0 / 0.0), the auxiliary furnace is resized to the primary furnace capacity and airflow.'
  end

  # human readable description of modeling approach
  def modeler_description
    return 'Runs after HPXMLtoOpenStudio (post-sizing). Reads the building EPW (path passed as an argument, or the model weather file as a fallback) and builds two hourly fraction schedules from the outdoor drybulb temperature: primary = 1.0 when T_odb >= switchover_temp else 0.0, auxiliary = 1.0 - primary. In each zone, the primary and auxiliary equipment are identified by the HPXML_ID of their components (HeatingSystem1 / HeatingSystem2) and their sequential heating fraction schedules are replaced with these two schedules. If both are air-loop furnaces and the auxiliary has the 1 Btu/h placeholder size (FractionHeatLoadServed = 0), its coil capacity, fan maximum flow, unitary heating airflow, air loop design flow and terminal maximum flow are copied from the primary furnace. No EMS and no HPXML schema change are used.'
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

    # Locate the two heating systems by HPXML_ID. The ID is carried by a component
    # (coil, boiler or zone HVAC), not necessarily by the zone equipment that owns
    # the sequential schedule (e.g., the air terminal of a furnace), so each tagged
    # object is expanded to the zone equipment it feeds. Other heating participants
    # (e.g., a room AC listed first in heating order) are left unchanged.
    primary_objects = hpxml_tagged_objects(model, PRIMARY_HPXML_ID)
    auxiliary_objects = hpxml_tagged_objects(model, AUXILIARY_HPXML_ID)
    if primary_objects.empty? || auxiliary_objects.empty?
      runner.registerError("Dual-fuel switchover requires model objects tagged '#{PRIMARY_HPXML_ID}' and '#{AUXILIARY_HPXML_ID}', found #{primary_objects.size} and #{auxiliary_objects.size}. Ensure both heating_system and heating_system_2 are defined.")
      return false
    end
    primary_handles = zone_equipment_handles(primary_objects)
    auxiliary_handles = zone_equipment_handles(auxiliary_objects)

    n_zones_applied = 0
    model.getThermalZones.each do |zone|
      heating_equip = zone.equipmentInHeatingOrder.select do |equip|
        !zone.sequentialHeatingFractionSchedule(equip).empty?
      end
      primary_list = heating_equip.select { |equip| primary_handles.include?(equip.handle.to_s) }
      auxiliary_list = heating_equip.select { |equip| auxiliary_handles.include?(equip.handle.to_s) }
      next if primary_list.empty? && auxiliary_list.empty?

      if primary_list.empty? || auxiliary_list.empty? || !(primary_list & auxiliary_list).empty?
        runner.registerError("Dual-fuel switchover requires distinct '#{PRIMARY_HPXML_ID}' and '#{AUXILIARY_HPXML_ID}' heating equipment in zone '#{zone.name}'.")
        return false
      end

      primary_equip = primary_list[0]
      auxiliary_equip = auxiliary_list[0]

      # A furnace sharing ducts with a central AC is modeled twice by
      # HPXMLtoOpenStudio (combined AC+furnace and standalone furnace). Disable the
      # extra copies so they cannot heat outside the switchover dispatch.
      (primary_list[1..] + auxiliary_list[1..]).each do |duplicate_equip|
        unless zone.setSequentialHeatingFractionSchedule(duplicate_equip, model.alwaysOffDiscreteSchedule)
          runner.registerError("Failed to disable duplicate heating equipment '#{duplicate_equip.name}' in zone '#{zone.name}'.")
          return false
        end
        runner.registerWarning("Disabled duplicate heating equipment '#{duplicate_equip.name}' in zone '#{zone.name}' (same HPXML system modeled twice).")
      end

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

    return false unless resize_auxiliary_furnace(runner, primary_objects, auxiliary_objects)

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

  # Returns the model objects tagged with the given HPXML_ID additional property.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @param hpxml_id [String] HPXML system ID (e.g., HeatingSystem1)
  # @return [Array<OpenStudio::Model::ModelObject>] Tagged model objects
  def hpxml_tagged_objects(model, hpxml_id)
    return model.getAdditionalPropertiess.select { |ap|
      id = ap.getFeatureAsString('HPXML_ID')
      id.is_initialized && id.get == hpxml_id
    }.map(&:modelObject)
  end

  # Returns the handles of every object that can be the zone equipment of the
  # tagged objects: the objects themselves, their parent unitary/zone HVAC, the
  # demand side of their air loop (air terminal) and of their plant loop
  # (baseboard coil and its zone HVAC).
  #
  # @param tagged_objects [Array<OpenStudio::Model::ModelObject>] Tagged model objects
  # @return [Array<String>] Candidate zone equipment handles
  def zone_equipment_handles(tagged_objects)
    candidates = []
    tagged_objects.each do |obj|
      comps = [obj]
      hvac_comp = obj.to_HVACComponent
      if hvac_comp.is_initialized
        hvac_comp = hvac_comp.get
        comps << hvac_comp.containingHVACComponent.get if hvac_comp.containingHVACComponent.is_initialized
        comps << hvac_comp.containingZoneHVACComponent.get if hvac_comp.containingZoneHVACComponent.is_initialized
      end
      comps.dup.each do |comp|
        comp = comp.to_HVACComponent
        next unless comp.is_initialized

        comp = comp.get
        comps.concat(comp.airLoopHVAC.get.demandComponents) if comp.airLoopHVAC.is_initialized
        next unless comp.plantLoop.is_initialized

        comp.plantLoop.get.demandComponents.each do |demand_comp|
          comps << demand_comp
          demand_hvac = demand_comp.to_HVACComponent
          next unless demand_hvac.is_initialized

          zone_hvac = demand_hvac.get.containingZoneHVACComponent
          comps << zone_hvac.get if zone_hvac.is_initialized
        end
      end
      candidates.concat(comps)
    end
    return candidates.map { |comp| comp.handle.to_s }.uniq
  end

  # Returns the components of an air-loop furnace (fuel or electric heating coil in
  # an AirLoopHVAC:UnitarySystem with a Fan:SystemModel), or nil.
  #
  # @param tagged_objects [Array<OpenStudio::Model::ModelObject>] Objects tagged with the system HPXML_ID
  # @return [Hash, nil] coil, unitary, fan, air_loop and terminals
  def furnace_components(tagged_objects)
    tagged_objects.each do |obj|
      coil = obj.to_CoilHeatingGas
      coil = obj.to_CoilHeatingElectric unless coil.is_initialized
      next unless coil.is_initialized

      coil = coil.get
      unitary = coil.containingHVACComponent
      next unless unitary.is_initialized

      unitary = unitary.get.to_AirLoopHVACUnitarySystem
      next unless unitary.is_initialized

      unitary = unitary.get
      next unless unitary.airLoopHVAC.is_initialized && unitary.supplyFan.is_initialized

      fan = unitary.supplyFan.get.to_FanSystemModel
      next unless fan.is_initialized

      air_loop = unitary.airLoopHVAC.get
      terminals = air_loop.demandComponents.map(&:to_AirTerminalSingleDuctConstantVolumeNoReheat).select(&:is_initialized).map(&:get)
      return { coil: coil, unitary: unitary, fan: fan.get, air_loop: air_loop, terminals: terminals }
    end
    return
  end

  # Resizes the auxiliary furnace to the primary furnace capacity and airflow when
  # the auxiliary was sized with FractionHeatLoadServed = 0 (1 Btu/h placeholder).
  # Both are furnaces with the same maximum supply air temperature, so capacity and
  # airflow are copied as-is. Fan power per flow is kept (own fan efficiency).
  #
  # @param runner [OpenStudio::Measure::OSRunner] Object used to display messages
  # @param primary_objects [Array<OpenStudio::Model::ModelObject>] Objects tagged HeatingSystem1
  # @param auxiliary_objects [Array<OpenStudio::Model::ModelObject>] Objects tagged HeatingSystem2
  # @return [Boolean] false on failure
  def resize_auxiliary_furnace(runner, primary_objects, auxiliary_objects)
    auxiliary = furnace_components(auxiliary_objects)
    return true if auxiliary.nil?

    aux_capacity = auxiliary[:coil].nominalCapacity
    return true if aux_capacity.is_initialized && aux_capacity.get >= PLACEHOLDER_CAPACITY_W

    primary = furnace_components(primary_objects)
    if primary.nil?
      runner.registerError("Auxiliary furnace '#{auxiliary[:coil].name}' has no heating capacity (FractionHeatLoadServed = 0) but '#{PRIMARY_HPXML_ID}' is not an air-loop furnace to copy the sizing from.")
      return false
    end

    capacity_w = primary[:coil].nominalCapacity
    airflow_m3s = primary[:unitary].supplyAirFlowRateDuringHeatingOperation
    unless capacity_w.is_initialized && airflow_m3s.is_initialized
      runner.registerError("Cannot read the heating capacity/airflow of primary furnace '#{primary[:coil].name}'.")
      return false
    end
    capacity_w = capacity_w.get
    airflow_m3s = airflow_m3s.get

    auxiliary[:coil].setNominalCapacity(capacity_w)
    auxiliary[:fan].setDesignMaximumAirFlowRate(airflow_m3s)
    auxiliary[:unitary].setSupplyAirFlowRateDuringHeatingOperation(airflow_m3s)
    auxiliary[:air_loop].setDesignSupplyAirFlowRate(airflow_m3s)
    auxiliary[:terminals].each { |terminal| terminal.setMaximumAirFlowRate(airflow_m3s) }

    runner.registerInfo("Resized auxiliary furnace '#{auxiliary[:coil].name}' to #{capacity_w.round(1)} W and #{airflow_m3s.round(5)} m3/s (copied from '#{primary[:coil].name}').")
    return true
  end
end

# register the measure to be used by the application
SetDualFuelHeatingSwitchover.new.registerWithApplication
