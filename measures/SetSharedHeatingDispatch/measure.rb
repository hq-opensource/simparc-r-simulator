# frozen_string_literal: true

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/

# start the measure
class SetSharedHeatingDispatch < OpenStudio::Measure::ModelMeasure
  PRIMARY_HPXML_ID = 'HeatingSystem1'
  AUXILIARY_HPXML_ID = 'HeatingSystem2'

  # human readable name
  def name
    return 'Set Shared Heating Dispatch'
  end

  # human readable description
  def description
    return 'Dispatches the two heating systems as a load share: the lead system takes a fixed fraction of the heating load (up to its capacity) and the other system takes everything that remains, including the load the lead system cannot serve when it is saturated. Sizing (capacity split) is left untouched.'
  end

  # human readable description of modeling approach
  def modeler_description
    return 'Runs after HPXMLtoOpenStudio (post-sizing). The lead system (HeatingSystem1 or HeatingSystem2, chosen by the caller, typically the smaller one) is moved to heating priority 1 and its sequential heating fraction schedule is replaced by a constant share_fraction schedule; the other system is moved to heating priority 2 with a constant 1.0 schedule. Because the zone uses SequentialLoad distribution, the lead system serves min(share_fraction * load, its capacity) and the second system serves the entire remaining load up to its own capacity. share_fraction = 1.0 gives a base-load/peaking cascade. No EMS and no HPXML schema change are used.'
  end

  # Define the arguments that the user will input.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @return [OpenStudio::Measure::OSArgumentVector] an OpenStudio::Measure::OSArgumentVector object
  def arguments(model) # rubocop:disable Lint/UnusedMethodArgument
    args = OpenStudio::Measure::OSArgumentVector.new

    arg = OpenStudio::Measure::OSArgument.makeBoolArgument('enabled', false)
    arg.setDisplayName('Enable Shared Heating Dispatch')
    arg.setDescription('If true, overrides the sequential heating fraction schedules and heating priorities to share the load between the two heating systems. If false, the measure does nothing (stock behavior is preserved).')
    arg.setDefaultValue(true)
    args << arg

    arg = OpenStudio::Measure::OSArgument.makeDoubleArgument('share_fraction', false)
    arg.setDisplayName('Lead System Share Fraction')
    arg.setDescription('Fraction (0-1] of the heating load requested from the lead system. The other system serves the remaining load.')
    arg.setUnits('Frac')
    arg.setDefaultValue(0.5)
    args << arg

    lead_choices = OpenStudio::StringVector.new
    lead_choices << PRIMARY_HPXML_ID
    lead_choices << AUXILIARY_HPXML_ID
    arg = OpenStudio::Measure::OSArgument.makeChoiceArgument('lead_hpxml_id', lead_choices, false)
    arg.setDisplayName('Lead Heating System')
    arg.setDescription("HPXML ID of the system placed first in the heating sequence. For the shared load to be fully served up to the sum of capacities, this must be the smaller system when share_fraction is 0.5.")
    arg.setDefaultValue(AUXILIARY_HPXML_ID)
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
      runner.registerAsNotApplicable('Shared heating dispatch disabled; leaving sequential heating fraction schedules unchanged.')
      return true
    end

    share_fraction = runner.getDoubleArgumentValue('share_fraction', user_arguments)
    lead_id = runner.getStringArgumentValue('lead_hpxml_id', user_arguments)

    unless share_fraction > 0.0 && share_fraction <= 1.0
      runner.registerError("share_fraction must be in (0, 1], got #{share_fraction}.")
      return false
    end

    follower_id = lead_id == PRIMARY_HPXML_ID ? AUXILIARY_HPXML_ID : PRIMARY_HPXML_ID

    # Locate the two heating systems by HPXML_ID (see SetDualFuelHeatingSwitchover).
    lead_objects = hpxml_tagged_objects(model, lead_id)
    follower_objects = hpxml_tagged_objects(model, follower_id)
    if lead_objects.empty? || follower_objects.empty?
      runner.registerError("Shared heating dispatch requires model objects tagged '#{PRIMARY_HPXML_ID}' and '#{AUXILIARY_HPXML_ID}', found #{lead_objects.size} (#{lead_id}) and #{follower_objects.size} (#{follower_id}). Ensure both heating_system and heating_system_2 are defined.")
      return false
    end
    lead_handles = zone_equipment_handles(lead_objects)
    follower_handles = zone_equipment_handles(follower_objects)

    lead_sch = OpenStudio::Model::ScheduleConstant.new(model)
    lead_sch.setName('Shared Heating Lead Fraction Schedule')
    lead_sch.setValue(share_fraction)

    follower_sch = OpenStudio::Model::ScheduleConstant.new(model)
    follower_sch.setName('Shared Heating Follower Fraction Schedule')
    follower_sch.setValue(1.0)

    n_zones_applied = 0
    model.getThermalZones.each do |zone|
      heating_equip = zone.equipmentInHeatingOrder.select do |equip|
        !zone.sequentialHeatingFractionSchedule(equip).empty?
      end
      lead_list = heating_equip.select { |equip| lead_handles.include?(equip.handle.to_s) }
      follower_list = heating_equip.select { |equip| follower_handles.include?(equip.handle.to_s) }
      next if lead_list.empty? && follower_list.empty?

      if lead_list.empty? || follower_list.empty? || !(lead_list & follower_list).empty?
        runner.registerError("Shared heating dispatch requires distinct '#{lead_id}' and '#{follower_id}' heating equipment in zone '#{zone.name}'.")
        return false
      end

      lead_equip = lead_list[0]
      follower_equip = follower_list[0]

      # A furnace sharing ducts with a central AC is modeled twice by
      # HPXMLtoOpenStudio (combined AC+furnace and standalone furnace). Disable the
      # extra copies so they cannot heat outside the shared dispatch.
      (lead_list[1..] + follower_list[1..]).each do |duplicate_equip|
        unless zone.setSequentialHeatingFractionSchedule(duplicate_equip, model.alwaysOffDiscreteSchedule)
          runner.registerError("Failed to disable duplicate heating equipment '#{duplicate_equip.name}' in zone '#{zone.name}'.")
          return false
        end
        runner.registerWarning("Disabled duplicate heating equipment '#{duplicate_equip.name}' in zone '#{zone.name}' (same HPXML system modeled twice).")
      end

      # Lead first, follower second in the heating sequence.
      unless zone.setHeatingPriority(follower_equip, 1) && zone.setHeatingPriority(lead_equip, 1)
        runner.registerError("Failed to set heating priorities in zone '#{zone.name}'.")
        return false
      end

      unless zone.setSequentialHeatingFractionSchedule(lead_equip, lead_sch)
        runner.registerError("Failed to set the lead sequential heating fraction schedule in zone '#{zone.name}'.")
        return false
      end
      unless zone.setSequentialHeatingFractionSchedule(follower_equip, follower_sch)
        runner.registerError("Failed to set the follower sequential heating fraction schedule in zone '#{zone.name}'.")
        return false
      end

      runner.registerInfo("Applied shared heating dispatch in zone '#{zone.name}': lead='#{lead_equip.name}' (fraction #{share_fraction.round(3)}), follower='#{follower_equip.name}' (fraction 1.0).")
      n_zones_applied += 1
    end

    if n_zones_applied == 0
      runner.registerAsNotApplicable('No zone with heating equipment and a sequential heating fraction schedule was found; nothing to override.')
      return true
    end

    runner.registerFinalCondition("Applied shared heating dispatch to #{n_zones_applied} zone(s): #{lead_id} serves #{(share_fraction * 100).round(1)}% of the load first, #{follower_id} serves the remainder.")
    return true
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
end

# register the measure to be used by the application
SetSharedHeatingDispatch.new.registerWithApplication
