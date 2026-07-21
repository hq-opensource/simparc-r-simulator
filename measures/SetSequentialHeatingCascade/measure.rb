# frozen_string_literal: true

# see the URL below for information on how to write OpenStudio measures
# http://nrel.github.io/OpenStudio-user-documentation/reference/measure_writing_guide/

# start the measure
class SetSequentialHeatingCascade < OpenStudio::Measure::ModelMeasure
  # human readable name
  def name
    return 'Set Sequential Heating Cascade'
  end

  # human readable description
  def description
    return 'Overrides the sequential heating fraction schedules of the heating equipment to 1.0 so that heating is dispatched as a base-load + peaking capacity cascade (system 1 = primary/base-load served first, system 2 = auxiliary/peaking served second). Sizing (capacity split) is left untouched.'
  end

  # human readable description of modeling approach
  def modeler_description
    return 'Runs after HPXMLtoOpenStudio (post-sizing). For every zone heating equipment that already has a sequential heating fraction schedule, replaces that schedule with a constant 1.0 schedule. Because the zone uses SequentialLoad distribution, the equipment in heating sequence 1 (system 1) then takes all the load it can up to its sized capacity (plateau) and the equipment in heating sequence 2 (system 2) picks up the residual, producing an emergent change point without modifying capacities, the HPXML schema, or using EMS.'
  end

  # Define the arguments that the user will input.
  #
  # @param model [OpenStudio::Model::Model] OpenStudio Model object
  # @return [OpenStudio::Measure::OSArgumentVector] an OpenStudio::Measure::OSArgumentVector object
  def arguments(model) # rubocop:disable Lint/UnusedMethodArgument
    args = OpenStudio::Measure::OSArgumentVector.new

    arg = OpenStudio::Measure::OSArgument.makeBoolArgument('enabled', false)
    arg.setDisplayName('Enable Heating Cascade')
    arg.setDescription('If true, overrides sequential heating fraction schedules to 1.0 to produce the base-load/peaking cascade. If false, the measure does nothing (stock behavior is preserved).')
    arg.setDefaultValue(true)
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
      runner.registerAsNotApplicable('Heating cascade disabled; leaving sequential heating fraction schedules unchanged.')
      return true
    end

    # Create a single reusable constant 1.0 fraction schedule.
    cascade_sch = OpenStudio::Model::ScheduleConstant.new(model)
    cascade_sch.setName('Sequential Heating Cascade Fraction Schedule')
    cascade_sch.setValue(1.0)

    n_overridden = 0
    model.getThermalZones.each do |zone|
      zone.equipment.each do |equip|
        # Only touch equipment that already participates in heating dispatch
        # (i.e. has a sequential heating fraction schedule assigned).
        existing_sch = zone.sequentialHeatingFractionSchedule(equip)
        next if existing_sch.empty?

        hpxml_id = equip.additionalProperties.getFeatureAsString('HPXML_ID')
        id_str = hpxml_id.is_initialized ? hpxml_id.get : equip.name.to_s

        success = zone.setSequentialHeatingFractionSchedule(equip, cascade_sch)
        unless success
          runner.registerError("Failed to set sequential heating fraction schedule for equipment '#{id_str}' in zone '#{zone.name}'.")
          return false
        end

        runner.registerInfo("Set sequential heating fraction to 1.0 for heating equipment '#{id_str}' (heating sequence position preserved) in zone '#{zone.name}'.")
        n_overridden += 1
      end
    end

    if n_overridden == 0
      runner.registerAsNotApplicable('No zone heating equipment with a sequential heating fraction schedule was found; nothing to override.')
      return true
    end

    runner.registerFinalCondition("Overrode sequential heating fraction schedules to 1.0 for #{n_overridden} heating equipment object(s); heating now dispatches as a base-load/peaking cascade.")
    return true
  end
end

# register the measure to be used by the application
SetSequentialHeatingCascade.new.registerWithApplication
